import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
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
  LayoutGrid, List, Heart, Shield, ArrowUpDown, ArrowUp, ArrowDown, Star
} from 'lucide-react';
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
import { NotificationBell } from '../components/notifications/NotificationBell';
import AddStudentWizard from '../components/wizards/AddStudentWizard';
import { AddTeacherWizard } from '../components/wizards/AddTeacherWizard';
import CreateClassWizard from '../components/wizards/CreateClassWizard';
import TeacherProfileDialog from '../components/management/TeacherProfileDialog';
import ParentProfileDialog from '../components/management/ParentProfileDialog';
import StudentClassGrid from '../components/management/StudentClassGrid';

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
  const t = THEME_COLORS.student;
  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${t.hoverBorder} cursor-pointer overflow-hidden`}
        onClick={() => onView(student)}>
        <div className={`h-0.5 ${t.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <StudentAvatar student={student} size="sm" />
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px]">{student.full_name}</h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{student.grade || '-'} • {student.section || student.class_name || '-'}</span>
            <span className="text-[10px] text-muted-foreground font-mono hidden md:inline">{student.student_number || student.id?.slice(0, 8)}</span>
          </div>
          <Badge variant={student.is_active !== false ? 'default' : 'destructive'}
            className={`text-[10px] h-5 rounded-full border-0 ${student.is_active !== false ? t.badge : ''}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${student.is_active !== false ? t.badgeDot : 'bg-red-500'}`} />
            {student.is_active !== false ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}
          </Badge>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(student)}><Eye className="h-3.5 w-3.5 me-2" />{isRTL ? 'عرض الملف الشخصي' : 'View Profile'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(student)}><Edit className="h-3.5 w-3.5 me-2" />{isRTL ? 'تعديل البيانات' : 'Edit Info'}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAction(student, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{isRTL ? 'إعادة تعيين كلمة المرور' : 'Reset Password'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDelete(student)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{isRTL ? 'حذف' : 'Delete'}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-border/50 ${t.hoverBorder} h-full cursor-pointer overflow-hidden`}
      onClick={() => onView(student)}>
      <div className={`h-1.5 ${t.bar}`} />
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
              <DropdownMenuItem onClick={() => onView(student)}><Eye className="h-3.5 w-3.5 me-2" />{isRTL ? 'عرض الملف الشخصي' : 'View Profile'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(student)}><Edit className="h-3.5 w-3.5 me-2" />{isRTL ? 'تعديل البيانات' : 'Edit Info'}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAction(student, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{isRTL ? 'إعادة تعيين كلمة المرور' : 'Reset Password'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAction(student, student.is_active !== false ? 'suspend' : 'activate')}>
                {student.is_active !== false ? <UserX className="h-3.5 w-3.5 me-2" /> : <UserCheck className="h-3.5 w-3.5 me-2" />}
                {student.is_active !== false ? (isRTL ? 'تعليق الحساب' : 'Suspend') : (isRTL ? 'تفعيل الحساب' : 'Activate')}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(student)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{isRTL ? 'حذف' : 'Delete'}</DropdownMenuItem>
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
            className={`text-[10px] h-5 rounded-full border-0 ${student.is_active !== false ? t.badge : ''}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${student.is_active !== false ? t.badgeDot : 'bg-red-500'}`} />
            {student.is_active !== false ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}
          </Badge>
          <ChevronRight className={`h-3.5 w-3.5 text-muted-foreground/30 group-hover:${t.accent} group-hover:translate-x-0.5 transition-all`} />
        </div>
      </CardContent>
    </Card>
  );
};

const TeacherCard = ({ teacher, isRTL, onEdit, onDelete, onView, onAction, viewMode = 'grid' }) => {
  const t = THEME_COLORS.teacher;
  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${t.hoverBorder} cursor-pointer overflow-hidden`}
        onClick={() => onView(teacher)}>
        <div className={`h-0.5 ${t.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <TeacherAvatar teacher={teacher} size="sm" />
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px]">{teacher.full_name}</h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{teacher.specialization || (isRTL ? 'معلم' : 'Teacher')}</span>
            <span className="text-xs text-muted-foreground hidden md:inline">{teacher.weekly_periods || teacher.sessions_count || '-'} {isRTL ? 'حصة/أسبوع' : 'sessions/wk'}</span>
          </div>
          <Badge className={`text-[10px] h-5 rounded-full border-0 ${teacher.is_active !== false ? t.badge : 'bg-red-100 text-red-700'}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${teacher.is_active !== false ? t.badgeDot : 'bg-red-500'}`} />
            {teacher.is_active !== false ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}
          </Badge>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(teacher)}><Eye className="h-3.5 w-3.5 me-2" />{isRTL ? 'عرض التفاصيل' : 'View Details'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(teacher)}><Edit className="h-3.5 w-3.5 me-2" />{isRTL ? 'تعديل البيانات' : 'Edit Info'}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(teacher)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{isRTL ? 'حذف' : 'Delete'}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-border/50 ${t.hoverBorder} h-full cursor-pointer overflow-hidden`}
      onClick={() => onView(teacher)}>
      <div className={`h-1.5 ${t.bar}`} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <TeacherAvatar teacher={teacher} />
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate max-w-[140px]">{teacher.full_name}</h3>
              <p className="text-[10px] text-muted-foreground truncate">{teacher.specialization || (isRTL ? 'معلم' : 'Teacher')}</p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(teacher)}><Eye className="h-3.5 w-3.5 me-2" />{isRTL ? 'عرض التفاصيل' : 'View Details'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(teacher)}><Edit className="h-3.5 w-3.5 me-2" />{isRTL ? 'تعديل البيانات' : 'Edit Info'}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAction(teacher, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{isRTL ? 'إعادة تعيين كلمة المرور' : 'Reset Password'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAction(teacher, teacher.is_active !== false ? 'suspend' : 'activate')}>
                {teacher.is_active !== false ? <UserX className="h-3.5 w-3.5 me-2" /> : <UserCheck className="h-3.5 w-3.5 me-2" />}
                {teacher.is_active !== false ? (isRTL ? 'تعليق الحساب' : 'Suspend') : (isRTL ? 'تفعيل الحساب' : 'Activate')}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(teacher)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{isRTL ? 'حذف' : 'Delete'}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="space-y-1.5 text-xs mb-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Award className="h-3 w-3 shrink-0" />
            <span className="truncate">{teacher.rank || (isRTL ? 'معلم' : 'Teacher')}</span>
            {teacher.years_of_experience > 0 && (
              <Badge variant="outline" className="text-[9px] h-4 px-1.5 border-muted-foreground/20">{teacher.years_of_experience} {isRTL ? 'سنة' : 'yrs'}</Badge>
            )}
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-3 w-3 shrink-0" />
            <span>{teacher.weekly_periods || teacher.sessions_count || '-'} {isRTL ? 'حصة/أسبوع' : 'sessions/wk'}</span>
          </div>
        </div>
        <div className="flex items-center justify-between pt-2.5 border-t border-border/40">
          <Badge className={`text-[10px] h-5 rounded-full border-0 ${teacher.is_active !== false ? t.badge : 'bg-red-100 text-red-700'}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${teacher.is_active !== false ? t.badgeDot : 'bg-red-500'}`} />
            {teacher.is_active !== false ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}
          </Badge>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-emerald-500 group-hover:translate-x-0.5 transition-all" />
        </div>
      </CardContent>
    </Card>
  );
};

const ParentCard = ({ parent, isRTL, onView, onAction, onDelete, viewMode = 'grid' }) => {
  const t = THEME_COLORS.parent;
  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${t.hoverBorder} cursor-pointer overflow-hidden`}
        onClick={() => onView(parent)}>
        <div className={`h-0.5 ${t.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <ParentAvatar parent={parent} size="sm" />
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px]">{parent.full_name}</h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{parent.relationship || (isRTL ? 'ولي أمر' : 'Parent')}</span>
            <span className="text-xs text-muted-foreground hidden md:inline">{parent.children_count || 0} {isRTL ? 'أبناء' : 'children'}</span>
          </div>
          <Badge className={`text-[10px] h-5 rounded-full border-0 ${t.badge}`}>
            <Heart className="h-2.5 w-2.5 me-1" />
            {parent.children_count || 0}
          </Badge>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-border/50 ${t.hoverBorder} h-full cursor-pointer overflow-hidden`}
      onClick={() => onView(parent)}>
      <div className={`h-1.5 ${t.bar}`} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <ParentAvatar parent={parent} />
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate max-w-[140px]">{parent.full_name}</h3>
              <p className="text-[10px] text-muted-foreground">{parent.relationship || (isRTL ? 'ولي أمر' : 'Parent')}</p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(parent)}><Eye className="h-3.5 w-3.5 me-2" />{isRTL ? 'عرض التفاصيل' : 'View Details'}</DropdownMenuItem>
              {parent.user_id && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => onAction(parent, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{isRTL ? 'إعادة تعيين كلمة المرور' : 'Reset Password'}</DropdownMenuItem>
                </>
              )}
              {onDelete && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => onDelete(parent)} className="text-red-600 focus:text-red-700 focus:bg-red-50">
                    <Trash2 className="h-3.5 w-3.5 me-2" />{isRTL ? 'حذف نهائي' : 'Delete Permanently'}
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
            <span>{parent.children_count || 0} {isRTL ? 'أبناء مسجلين' : 'registered children'}</span>
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
          <Badge className={`text-[10px] h-5 rounded-full border-0 ${t.badge}`}>
            <Shield className="h-2.5 w-2.5 me-1" />
            {parent.relationship || (isRTL ? 'ولي أمر' : 'Parent')}
          </Badge>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-amber-500 group-hover:translate-x-0.5 transition-all" />
        </div>
      </CardContent>
    </Card>
  );
};

const ClassCard = ({ classItem, isRTL, onEdit, onDelete, onView, viewMode = 'grid' }) => {
  const pct = Math.min(100, ((classItem.student_count || 0) / (classItem.capacity || 30)) * 100);
  const t = THEME_COLORS.class;

  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${t.hoverBorder} cursor-pointer overflow-hidden`}
        onClick={() => onView(classItem)}>
        <div className={`h-0.5 ${t.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${t.gradient} flex items-center justify-center shrink-0`}>
            <Building2 className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px]">{classItem.name}</h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{classItem.grade} - {classItem.section}</span>
            <span className="text-xs text-muted-foreground hidden md:inline">{classItem.student_count || 0}/{classItem.capacity || 30}</span>
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
              <DropdownMenuItem onClick={() => onView(classItem)}><Eye className="h-3.5 w-3.5 me-2" />{isRTL ? 'عرض التفاصيل' : 'View Details'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(classItem)}><Edit className="h-3.5 w-3.5 me-2" />{isRTL ? 'تعديل' : 'Edit'}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(classItem)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{isRTL ? 'حذف' : 'Delete'}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg transition-all duration-200 border-border/50 ${t.hoverBorder} h-full cursor-pointer`}
      onClick={() => onView(classItem)}>
      <div className={`h-1.5 rounded-t-lg ${t.bar}`} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${t.gradient} flex items-center justify-center shadow-sm`}>
              <Building2 className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate">{classItem.name}</h3>
              <p className="text-[11px] text-muted-foreground">{classItem.grade} - {classItem.section}</p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(classItem)}><Eye className="h-3.5 w-3.5 me-2" />{isRTL ? 'عرض التفاصيل' : 'View Details'}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(classItem)}><Edit className="h-3.5 w-3.5 me-2" />{isRTL ? 'تعديل' : 'Edit'}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(classItem)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{isRTL ? 'حذف' : 'Delete'}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
          <Users className="h-3 w-3 shrink-0" />
          <span>{classItem.student_count || 0} / {classItem.capacity || 30} {isRTL ? 'طالب' : 'students'}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
          <UserCheck className="h-3 w-3 shrink-0" />
          <span className="truncate">{classItem.homeroom_teacher_name || (isRTL ? 'لم يُعين' : 'Not assigned')}</span>
        </div>
        <div className="mb-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-medium text-muted-foreground">{Math.round(pct)}% {isRTL ? 'ممتلئ' : 'full'}</span>
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
  const [panelOpen, setPanelOpen] = useState(false);
  const [currentBubble, setCurrentBubble] = useState(0);
  const hasInsights = insights && insights.length > 0 && insights.some(i => i.severity !== 'success');

  const bubbleMessages = useMemo(() => {
    const msgs = [];
    if (hasInsights) {
      const highCount = insights.filter(i => i.severity === 'high').length;
      if (highCount > 0) msgs.push(isRTL ? `لدي ${highCount} تنبيهات مهمة تحتاج انتباهك!` : `I have ${highCount} critical alerts for you!`);
      insights.forEach(i => {
        if (i.severity === 'high' || i.severity === 'medium') msgs.push(i.message);
      });
    }
    if (!hasInsights || msgs.length === 0) {
      msgs.push(isRTL ? 'كل شيء يبدو رائعًا! أحسنت' : 'Everything looks great! Well done');
    }
    if (stats) {
      msgs.push(isRTL ? `لديك ${stats.totalStudents} طالب و ${stats.totalTeachers} معلم` : `You have ${stats.totalStudents} students and ${stats.totalTeachers} teachers`);
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
                <h4 className="font-bold text-sm">{isRTL ? 'تحليلات حكيم' : 'Hakim Analysis'}</h4>
                <p className="text-[10px] text-white/70">{isRTL ? `${insights.length} ملاحظة تحتاج مراجعة` : `${insights.length} items need review`}</p>
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
                      insight.severity === 'high' ? 'border-red-300 text-red-700 hover:bg-red-100' :
                      insight.severity === 'medium' ? 'border-amber-300 text-amber-700 hover:bg-amber-100' :
                      'border-violet-300 text-violet-700 hover:bg-violet-100'
                    }`}
                    onClick={() => { onAction(insight.action, insight.data); setPanelOpen(false); }}>
                    <ArrowRight className="h-3 w-3 me-1" />
                    {isRTL ? 'عرض' : 'View'}
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
                {isRTL ? `عرض ${insights.length} ملاحظات ←` : `View ${insights.length} insights →`}
              </button>
            )}
          </div>
        </div>
      )}

      <div className="relative group cursor-pointer" onClick={() => setPanelOpen(!panelOpen)}
        title={isRTL ? 'حكيم - المساعد الذكي' : 'Hakim - Smart Assistant'}>
        <div className={`w-[72px] h-[72px] rounded-full overflow-hidden bg-white shadow-xl ring-3 ${hasInsights ? 'ring-violet-400 animate-[hakim-ring-pulse_2s_ease-in-out_infinite]' : 'ring-violet-200'} flex items-center justify-center transition-all duration-300 group-hover:scale-110 group-hover:shadow-2xl`}>
          <img src="/hakim-poses/detecting-patterns.png" alt="Hakim" className="hakim-img w-20 h-20 object-contain animate-[hakim-alive_4s_ease-in-out_infinite]"
            onError={(e) => { e.target.style.display = 'none'; e.target.parentElement.innerHTML = '<span class="text-3xl">🧠</span>'; }} />
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

const AddPickerDialog = ({ open, onClose, isRTL, onSelect }) => (
  <Dialog open={open} onOpenChange={(val) => { if (!val) onClose(); }}>
    <DialogContent className="sm:max-w-[480px]">
      <DialogHeader>
        <DialogTitle className="text-center text-lg">{isRTL ? 'إضافة عنصر جديد' : 'Add New Item'}</DialogTitle>
        <DialogDescription className="text-center">{isRTL ? 'اختر نوع العنصر الذي تريد إضافته' : 'Choose what you want to add'}</DialogDescription>
      </DialogHeader>
      <div className="grid grid-cols-3 gap-4 py-4">
        <button onClick={() => onSelect('student')}
          className="group p-5 rounded-xl border-2 border-border hover:border-[#1B2A4A] hover:bg-blue-50/50 dark:hover:bg-blue-950/10 transition-all text-center">
          <div className={`w-14 h-14 mx-auto mb-3 rounded-full bg-gradient-to-br ${THEME_COLORS.student.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
            <GraduationCap className="h-7 w-7 text-white" />
          </div>
          <p className="font-semibold text-sm">{isRTL ? 'طالب' : 'Student'}</p>
          <p className="text-[11px] text-muted-foreground mt-1">{isRTL ? 'إضافة طالب جديد' : 'Add new student'}</p>
        </button>
        <button onClick={() => onSelect('teacher')}
          className="group p-5 rounded-xl border-2 border-border hover:border-emerald-500 hover:bg-emerald-50/50 dark:hover:bg-emerald-950/10 transition-all text-center">
          <div className={`w-14 h-14 mx-auto mb-3 rounded-full bg-gradient-to-br ${THEME_COLORS.teacher.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
            <UserPlus className="h-7 w-7 text-white" />
          </div>
          <p className="font-semibold text-sm">{isRTL ? 'معلم' : 'Teacher'}</p>
          <p className="text-[11px] text-muted-foreground mt-1">{isRTL ? 'إضافة معلم جديد' : 'Add new teacher'}</p>
        </button>
        <button onClick={() => onSelect('class')}
          className="group p-5 rounded-xl border-2 border-border hover:border-purple-500 hover:bg-purple-50/50 dark:hover:bg-purple-950/10 transition-all text-center">
          <div className={`w-14 h-14 mx-auto mb-3 rounded-xl bg-gradient-to-br ${THEME_COLORS.class.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
            <School className="h-7 w-7 text-white" />
          </div>
          <p className="font-semibold text-sm">{isRTL ? 'فصل' : 'Class'}</p>
          <p className="text-[11px] text-muted-foreground mt-1">{isRTL ? 'إنشاء فصل جديد' : 'Create new class'}</p>
        </button>
      </div>
    </DialogContent>
  </Dialog>
);

export default function UsersClassesManagement() {
  const { user, api, schoolContext, isImpersonating } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const { nassaqConfirm, nassaqError, nassaqWarning } = useNassaqAlert();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(searchParams.get('filter') || 'students');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid');
  const [sortBy, setSortBy] = useState('name_asc');
  const [studentSubTab, setStudentSubTab] = useState('all');

  const [students, setStudents] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [parents, setParents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [grades, setGrades] = useState([]);

  const [showAddPicker, setShowAddPicker] = useState(false);
  const [showStudentWizard, setShowStudentWizard] = useState(false);
  const [showTeacherWizard, setShowTeacherWizard] = useState(false);
  const [showClassWizard, setShowClassWizard] = useState(false);

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
    totalClasses: classes.length,
    activeStudents: students.filter(s => s.is_active !== false).length,
    activeTeachers: teachers.filter(t => t.is_active !== false).length,
  }), [students, teachers, parents, classes]);

  const hakimInsights = useMemo(() => {
    const ins = [];
    if (studentsNoParent.length > 0) {
      ins.push({
        message: isRTL ? `${studentsNoParent.length} طالب بدون ولي أمر مسجّل` : `${studentsNoParent.length} students have no registered parent`,
        suggestion: isRTL ? 'يجب إضافة بيانات ولي الأمر لتفعيل التواصل مع الأسرة' : 'Add parent info to enable family communication',
        severity: 'high', action: 'show_students_no_parent', data: studentsNoParent
      });
    }
    if (studentsNoClass.length > 0) {
      ins.push({
        message: isRTL ? `${studentsNoClass.length} طالب لم يتم إسنادهم إلى أي فصل` : `${studentsNoClass.length} students not assigned to any class`,
        suggestion: isRTL ? 'قم بتعيين فصل لكل طالب لضمان انتظام الجدول' : 'Assign classes to ensure schedule works properly',
        severity: 'high', action: 'show_students_no_class', data: studentsNoClass
      });
    }
    if (teachersNoSubject.length > 0) {
      ins.push({
        message: isRTL ? `${teachersNoSubject.length} معلم بدون مادة مُسندة` : `${teachersNoSubject.length} teachers have no subject assigned`,
        suggestion: isRTL ? 'أسند مادة لكل معلم لإعداد الجدول الزمني' : 'Assign subjects to enable timetable generation',
        severity: 'medium', action: 'show_teachers_no_subject', data: teachersNoSubject
      });
    }
    if (accountsNoEmail.length > 0) {
      ins.push({
        message: isRTL ? `${accountsNoEmail.length} حساب بدون بريد إلكتروني` : `${accountsNoEmail.length} accounts missing email`,
        suggestion: isRTL ? 'البريد الإلكتروني مطلوب لتسجيل الدخول والإشعارات' : 'Email is needed for login and notifications',
        severity: 'low', action: 'show_no_email', data: accountsNoEmail
      });
    }
    if (suspendedStudents.length > 0) {
      ins.push({
        message: isRTL ? `${suspendedStudents.length} حساب طالب معلّق حالياً` : `${suspendedStudents.length} student accounts suspended`,
        suggestion: isRTL ? 'راجع الحسابات المعلقة وقرر إعادة تفعيلها أو حذفها' : 'Review suspended accounts and reactivate or remove',
        severity: 'medium', action: 'show_suspended', data: suspendedStudents
      });
    }
    if (overCapClasses.length > 0) {
      ins.push({
        message: isRTL ? `${overCapClasses.length} فصل تجاوز السعة` : `${overCapClasses.length} classes over capacity`,
        suggestion: isRTL ? 'أعد توزيع الطلاب أو زِد سعة الفصول' : 'Redistribute students or increase class capacity',
        severity: 'high', action: 'show_over_capacity', data: overCapClasses
      });
    }
    if (ins.length === 0) {
      ins.push({
        message: isRTL ? 'جميع البيانات مكتملة ومنظمة — أحسنت!' : 'All data is complete and organized — great job!',
        severity: 'success'
      });
    }
    return ins;
  }, [studentsNoParent, studentsNoClass, teachersNoSubject, accountsNoEmail, suspendedStudents, overCapClasses, isRTL]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchAllData(); }, [user, schoolContext]);
  useEffect(() => {
    if (activeTab && activeTab !== 'all') setSearchParams({ filter: activeTab });
    else setSearchParams({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const headers = {};
      if (isImpersonating && schoolContext?.school_id) headers['X-School-Context'] = schoolContext.school_id;
      const [studentsRes, teachersRes, classesRes, gradesRes, parentsRes] = await Promise.all([
        api.get('/students', { headers }).catch(() => ({ data: [] })),
        api.get('/teachers', { headers }).catch(() => ({ data: [] })),
        api.get('/classes', { headers }).catch(() => ({ data: [] })),
        api.get('/reference/grades', { headers }).catch(() => ({ data: [] })),
        api.get('/parents', { headers }).catch(() => ({ data: [] })),
      ]);
      setStudents(Array.isArray(studentsRes.data) ? studentsRes.data : []);
      setTeachers(Array.isArray(teachersRes.data) ? teachersRes.data : []);
      setClasses(Array.isArray(classesRes.data) ? classesRes.data : []);
      setGrades(Array.isArray(gradesRes.data) ? gradesRes.data : []);
      setParents(Array.isArray(parentsRes.data) ? parentsRes.data : []);
    } catch (error) {
      console.error('Error fetching data:', error);
      nassaqError(isRTL ? 'خطأ في تحميل البيانات' : 'Error loading data');
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

  const giftedStudents = useMemo(() => filteredStudents.filter(s => s.is_gifted), [filteredStudents]);
  const otherStudents = useMemo(() => filteredStudents.filter(s => !s.is_gifted), [filteredStudents]);
  const displayedStudents = useMemo(() => {
    if (studentSubTab === 'gifted') return giftedStudents;
    if (studentSubTab === 'other') return otherStudents;
    return filteredStudents;
  }, [studentSubTab, filteredStudents, giftedStudents, otherStudents]);

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
    let list = classes;
    if (activeFilter === 'overCapacity') list = overCapClasses;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(c => c.name?.toLowerCase().includes(q));
    }
    return applySorting(list, 'class');
  }, [classes, searchQuery, activeFilter, overCapClasses, applySorting]);

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

  const handleDelete = (item, type) => {
    const typeLabels = { student: isRTL ? 'الطالب' : 'student', teacher: isRTL ? 'المعلم' : 'teacher', parent: isRTL ? 'ولي الأمر' : 'parent', class: isRTL ? 'الفصل' : 'class' };
    const msg = isRTL
      ? `هل أنت متأكد من حذف ${typeLabels[type]}؟ سيتم حذف جميع البيانات المرتبطة نهائياً.`
      : `Are you sure you want to delete this ${type}? All related data will be permanently removed.`;
    nassaqConfirm(msg, async () => {
      try {
        const endpoints = { student: `/students/${item.id}`, teacher: `/teachers/${item.id}`, parent: `/parents/${item.id}`, class: `/classes/${item.id}` };
        const ep = endpoints[type];
        const res = await api.delete(ep);
        const cleanup = res.data?.cleanup;
        let successMsg = isRTL ? 'تم الحذف بنجاح' : 'Deleted successfully';
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
        let errMsg = isRTL ? 'فشل الحذف' : 'Delete failed';
        if (error.response?.data?.detail) {
          errMsg = typeof error.response.data.detail === 'string' ? error.response.data.detail : errMsg;
        }
        nassaqError(errMsg);
      }
    }, { title: isRTL ? 'تأكيد الحذف النهائي' : 'Confirm Permanent Delete', confirmText: isRTL ? 'نعم، احذف نهائياً' : 'Yes, Delete Permanently', cancelText: isRTL ? 'إلغاء' : 'Cancel' });
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
          toast.success(isRTL ? `تم إعادة تعيين كلمة المرور إلى: ${tempPass}` : `Password reset to: ${tempPass}`);
          break;
        }
        case 'suspend':
          await api.put(`/principal/${entityType}/${entityId}/status`, { status: 'suspended' });
          toast.success(isRTL ? 'تم تعليق الحساب' : 'Account suspended');
          fetchAllData();
          break;
        case 'activate':
          await api.put(`/principal/${entityType}/${entityId}/status`, { status: 'active' });
          toast.success(isRTL ? 'تم تفعيل الحساب' : 'Account activated');
          fetchAllData();
          break;
        default: break;
      }
    } catch (error) {
      const msg = error.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشلت العملية' : 'Operation failed'));
    }
  };

  const handleTransferStudent = async (studentId, targetClassId, studentName, className) => {
    const movingStudent = students.find(s => s.id === studentId);
    const oldClassId = movingStudent?.class_id;
    try {
      const headers = {};
      if (isImpersonating && schoolContext?.school_id) headers['X-School-Context'] = schoolContext.school_id;
      const res = await api.post('/students/transfer-class', { student_id: studentId, target_class_id: targetClassId }, { headers });
      if (res.data?.success) {
        toast.success(isRTL ? `تم نقل ${studentName} إلى ${className}` : `${studentName} transferred to ${className}`);
        setStudents(prev => prev.map(s => s.id === studentId ? { ...s, class_id: targetClassId, class_name: className } : s));
        setClasses(prev => prev.map(c => {
          if (c.id === targetClassId) {
            const ids = new Set(c.student_ids || []);
            ids.add(studentId);
            return { ...c, student_count: ids.size, student_ids: [...ids] };
          }
          if (oldClassId && c.id === oldClassId) {
            const ids = (c.student_ids || []).filter(id => id !== studentId);
            return { ...c, student_count: ids.length, student_ids: ids };
          }
          return c;
        }));
      }
    } catch (error) {
      const msg = error.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشل نقل الطالب' : 'Failed to transfer student'));
    }
  };

  const clearFilter = () => setActiveFilter(null);

  const handleHakimAction = (action, data) => {
    switch (action) {
      case 'show_students_no_parent':
        setActiveTab('students'); setSearchQuery(''); setActiveFilter('noParent');
        toast.info(isRTL ? `عرض ${data.length} طالب بدون ولي أمر — يحتاجون لتعديل بياناتهم` : `Showing ${data.length} students without parent — need data update`);
        break;
      case 'show_students_no_class':
        setActiveTab('students'); setSearchQuery(''); setActiveFilter('noClass');
        toast.info(isRTL ? `عرض ${data.length} طالب بدون فصل` : `Showing ${data.length} students without class`);
        break;
      case 'show_teachers_no_subject':
        setActiveTab('teachers'); setSearchQuery(''); setActiveFilter('noSubject');
        toast.info(isRTL ? `عرض ${data.length} معلم بدون مادة` : `Showing ${data.length} teachers without subject`);
        break;
      case 'show_no_email':
        setActiveTab('students'); setSearchQuery(''); setActiveFilter('noEmail');
        toast.info(isRTL ? `${data.length} حساب بدون بريد إلكتروني` : `${data.length} accounts without email`);
        break;
      case 'show_suspended':
        setActiveTab('students'); setSearchQuery(''); setActiveFilter('suspended');
        toast.info(isRTL ? `عرض ${data.length} حساب معلق` : `Showing ${data.length} suspended accounts`);
        break;
      case 'show_over_capacity':
        setActiveTab('classes'); setSearchQuery(''); setActiveFilter('overCapacity');
        toast.info(isRTL ? `عرض ${data.length} فصل تجاوز السعة` : `Showing ${data.length} over-capacity classes`);
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
        nassaqWarning(isRTL ? 'لا توجد تغييرات' : 'No changes');
        setEditLoading(false);
        return;
      }
      await api.put(ep, updateData);
      const entityLabel = selectedItemType === 'student' ? (isRTL ? 'الطالب' : 'student') : selectedItemType === 'teacher' ? (isRTL ? 'المعلم' : 'teacher') : (isRTL ? 'الفصل' : 'class');
      toast.success(isRTL ? `تم حفظ بيانات ${entityLabel} في قاعدة البيانات بنجاح` : `${entityLabel} data saved to database successfully`);
      setEditDialogOpen(false);
      setSelectedItem(null);
      fetchAllData();
    } catch (error) {
      let errMsg = isRTL ? 'فشل الحفظ' : 'Save failed';
      if (error.response?.data?.detail) {
        errMsg = typeof error.response.data.detail === 'string' ? error.response.data.detail : errMsg;
      }
      nassaqError(errMsg);
    } finally { setEditLoading(false); }
  };

  const handleRefresh = () => { fetchAllData(); toast.success(isRTL ? 'تم تحديث البيانات' : 'Data refreshed'); };
  const handleStudentCreated = () => { setShowStudentWizard(false); fetchAllData(); };
  const handleTeacherCreated = () => { setShowTeacherWizard(false); fetchAllData(); };
  const handleClassCreated = () => { setShowClassWizard(false); fetchAllData(); };

  const [downloadingTemplate, setDownloadingTemplate] = useState(false);

  const downloadTemplate = async (type) => {
    setDownloadingTemplate(true);
    try {
      const response = await api.get(`/bulk/template/${type}`, { responseType: 'blob' });
      const contentType = response.headers['content-type'] || '';
      if (!contentType.includes('spreadsheet') && !contentType.includes('octet-stream') && !contentType.includes('excel')) {
        throw new Error(isRTL ? 'الاستجابة ليست ملف صالح' : 'Response is not a valid file');
      }
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      const disposition = response.headers['content-disposition'];
      let filename = type === 'students' ? 'قالب_استيراد_الطلاب.xlsx' : 'قالب_استيراد_المعلمين.xlsx';
      if (disposition) {
        try {
          const starMatch = disposition.match(/filename\*=(?:UTF-8''|utf-8'')([^\s;]+)/i);
          const plainMatch = disposition.match(/filename[^;=\n]*=(['"]?)([^'"\n]*)\1/);
          if (starMatch?.[1]) filename = decodeURIComponent(starMatch[1]);
          else if (plainMatch?.[2]) filename = decodeURIComponent(plainMatch[2]);
        } catch { }
      }
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(isRTL ? 'تم تحميل القالب بنجاح' : 'Template downloaded successfully');
    } catch (err) {
      console.error('Template download error:', err);
      nassaqError(err.message || (isRTL ? 'فشل تحميل القالب — تأكد من تسجيل الدخول وحاول مرة أخرى' : 'Template download failed — check login and try again'));
    } finally {
      setDownloadingTemplate(false);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (!['.xlsx', '.xls', '.csv'].some(t => file.name.toLowerCase().endsWith(t))) {
        nassaqWarning(isRTL ? 'صيغة غير مدعومة' : 'Unsupported format');
        return;
      }
      setSelectedFile(file);
      setImportResult(null);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) { nassaqWarning(isRTL ? 'اختر ملفاً' : 'Select a file'); return; }
    setImporting(true); setImportResult(null);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      const response = await api.post(`/bulk/import/${importType}`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setImportResult(response.data);
      if (response.data.success) { toast.success(isRTL ? `تم استيراد ${response.data.imported} سجل` : `Imported ${response.data.imported} records`); fetchAllData(); }
      else nassaqWarning(isRTL ? `تم استيراد ${response.data.imported} من ${response.data.total_rows}` : `Imported ${response.data.imported} of ${response.data.total_rows}`);
    } catch (error) { nassaqError(error.response?.data?.detail || (isRTL ? 'فشل الاستيراد' : 'Import failed')); }
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
      toast.success(isRTL ? 'تم التصدير' : 'Exported');
    } catch (error) { nassaqError(isRTL ? 'فشل التصدير' : 'Export failed'); }
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
    const subTabs = [
      { key: 'all', label: isRTL ? 'جميع الطلاب' : 'All Students', icon: Users, count: filteredStudents.length },
      { key: 'gifted', label: isRTL ? 'الطلاب الموهوبين' : 'Gifted Students', icon: Star, count: giftedStudents.length },
      { key: 'other', label: isRTL ? 'الطلاب الآخرون' : 'Other Students', icon: GraduationCap, count: otherStudents.length },
    ];

    return (
      <div className="space-y-4">
        <div className="flex items-center gap-1.5 p-1 bg-muted/50 rounded-xl w-fit">
          {subTabs.map(tab => {
            const Icon = tab.icon;
            const isActive = studentSubTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setStudentSubTab(tab.key)}
                className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium transition-all duration-200
                  ${isActive
                    ? tab.key === 'gifted'
                      ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-md shadow-amber-500/20'
                      : 'bg-white dark:bg-gray-800 text-foreground shadow-md'
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/50 dark:hover:bg-gray-800/50'}`}
              >
                <Icon className={`h-3.5 w-3.5 ${isActive && tab.key === 'gifted' ? 'fill-white' : tab.key === 'gifted' && !isActive ? 'text-amber-500 fill-amber-500' : ''}`} />
                {tab.label}
                <Badge variant="secondary" className={`ms-1 h-4.5 text-[10px] px-1.5 rounded-full
                  ${isActive && tab.key === 'gifted' ? 'bg-white/20 text-white border-0' : isActive ? 'bg-muted' : 'bg-transparent'}`}>
                  {tab.count}
                </Badge>
              </button>
            );
          })}
        </div>

        {studentSubTab === 'gifted' && giftedStudents.length > 0 && (
          <div className="flex items-center gap-2 p-2.5 px-4 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200/60 dark:border-amber-800/40">
            <Star className="h-4 w-4 text-amber-500 fill-amber-500 shrink-0" />
            <span className="text-xs text-amber-700 dark:text-amber-300">
              {isRTL ? `${giftedStudents.length} طالب موهوب مسجّل` : `${giftedStudents.length} gifted student${giftedStudents.length !== 1 ? 's' : ''} enrolled`}
            </span>
          </div>
        )}

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
          <p className="text-muted-foreground font-medium">{isRTL ? 'لا توجد نتائج' : 'No results found'}</p>
          <p className="text-sm text-muted-foreground/60 mt-1">
            {searchQuery ? (isRTL ? 'جرّب تغيير كلمة البحث' : 'Try a different search') : (isRTL ? 'أضف عنصراً جديداً' : 'Add a new item to start')}
          </p>
          {!searchQuery && type !== 'parents' && (
            <Button variant="outline" className="mt-4" onClick={() => setShowAddPicker(true)}>
              <Plus className="h-4 w-4 me-1.5" />{isRTL ? 'إضافة' : 'Add New'}
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
                onView={(c) => handleView(c, 'class')} />
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
              onView={(c) => handleView(c, 'class')} />
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
              <h1 className="font-cairo text-2xl font-bold">{isRTL ? 'إدارة المستخدمين والفصول' : 'Users & Classes Management'}</h1>
              <p className="text-sm text-muted-foreground font-tajawal">{isRTL ? 'مركز الإدارة الشامل للحسابات والفصول الدراسية' : 'Comprehensive management center for accounts and classes'}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={() => setShowAddPicker(true)} className="bg-brand-turquoise hover:bg-brand-turquoise/90 rounded-xl h-10 shadow-md">
                <Plus className="h-4 w-4 me-1.5" />{isRTL ? 'إضافة' : 'Add'}
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleLanguage}><Globe className="h-5 w-5" /></Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme}>{isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</Button>
              <NotificationBell />
            </div>
          </div>
        </header>

        <main className="p-6 space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Card className={`${THEME_COLORS.student.bg} ${THEME_COLORS.student.border} cursor-pointer hover:shadow-md transition-shadow`}
              onClick={() => handleStatClick('students')}>
              <CardContent className="p-4 text-center">
                <GraduationCap className={`h-7 w-7 mx-auto mb-2 ${THEME_COLORS.student.icon}`} />
                <p className="text-2xl font-bold">{stats.totalStudents}</p>
                <p className="text-[11px] text-muted-foreground">{isRTL ? 'إجمالي الطلاب' : 'Total Students'}</p>
              </CardContent>
            </Card>
            <Card className={`${THEME_COLORS.parent.bg} ${THEME_COLORS.parent.border} cursor-pointer hover:shadow-md transition-shadow`}
              onClick={() => handleStatClick('parents')}>
              <CardContent className="p-4 text-center">
                <Heart className={`h-7 w-7 mx-auto mb-2 ${THEME_COLORS.parent.icon}`} />
                <p className="text-2xl font-bold">{stats.totalParents}</p>
                <p className="text-[11px] text-muted-foreground">{isRTL ? 'إجمالي أولياء الأمور' : 'Total Parents'}</p>
              </CardContent>
            </Card>
            <Card className={`${THEME_COLORS.teacher.bg} ${THEME_COLORS.teacher.border} cursor-pointer hover:shadow-md transition-shadow`}
              onClick={() => handleStatClick('teachers')}>
              <CardContent className="p-4 text-center">
                <UserCheck className={`h-7 w-7 mx-auto mb-2 ${THEME_COLORS.teacher.icon}`} />
                <p className="text-2xl font-bold">{stats.totalTeachers}</p>
                <p className="text-[11px] text-muted-foreground">{isRTL ? 'إجمالي المعلمين' : 'Total Teachers'}</p>
              </CardContent>
            </Card>
            <Card className={`${THEME_COLORS.class.bg} ${THEME_COLORS.class.border} cursor-pointer hover:shadow-md transition-shadow`}
              onClick={() => handleStatClick('classes')}>
              <CardContent className="p-4 text-center">
                <Building2 className={`h-7 w-7 mx-auto mb-2 ${THEME_COLORS.class.icon}`} />
                <p className="text-2xl font-bold">{stats.totalClasses}</p>
                <p className="text-[11px] text-muted-foreground">{isRTL ? 'إجمالي الفصول' : 'Total Classes'}</p>
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <Tabs value={activeTab} onValueChange={(v) => { setActiveTab(v); setActiveFilter(null); }} className="w-auto">
              <TabsList className="bg-muted/50 rounded-xl h-10">
                <TabsTrigger value="students" className="rounded-lg text-xs px-4" data-testid="filter-students">
                  <GraduationCap className="h-3.5 w-3.5 me-1.5" />
                  {isRTL ? 'الطلاب' : 'Students'} <Badge variant="secondary" className="ms-1.5 h-5 text-[10px] px-1.5">{filteredStudents.length}</Badge>
                </TabsTrigger>
                <TabsTrigger value="parents" className="rounded-lg text-xs px-4" data-testid="filter-parents">
                  <Heart className="h-3.5 w-3.5 me-1.5" />
                  {isRTL ? 'أولياء الأمور' : 'Parents'} <Badge variant="secondary" className="ms-1.5 h-5 text-[10px] px-1.5">{filteredParents.length}</Badge>
                </TabsTrigger>
                <TabsTrigger value="teachers" className="rounded-lg text-xs px-4" data-testid="filter-teachers">
                  <UserCheck className="h-3.5 w-3.5 me-1.5" />
                  {isRTL ? 'المعلمين' : 'Teachers'} <Badge variant="secondary" className="ms-1.5 h-5 text-[10px] px-1.5">{filteredTeachers.length}</Badge>
                </TabsTrigger>
                <TabsTrigger value="classes" className="rounded-lg text-xs px-4" data-testid="filter-classes">
                  <Building2 className="h-3.5 w-3.5 me-1.5" />
                  {isRTL ? 'الفصول' : 'Classes'} <Badge variant="secondary" className="ms-1.5 h-5 text-[10px] px-1.5">{filteredClasses.length}</Badge>
                </TabsTrigger>
                <TabsTrigger value="import-export" className="rounded-lg text-xs px-4">
                  <FileSpreadsheet className="h-3.5 w-3.5 me-1.5" />
                  {isRTL ? 'استيراد/تصدير' : 'Import/Export'}
                </TabsTrigger>
              </TabsList>
            </Tabs>

            <div className="flex items-center gap-2 ms-auto">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="rounded-xl h-10 gap-2 px-3">
                    <ArrowUpDown className="h-4 w-4" />
                    <span className="text-xs hidden sm:inline">
                      {sortBy === 'name_asc' ? (isRTL ? 'أبجدي أ-ي' : 'A-Z') :
                       sortBy === 'name_desc' ? (isRTL ? 'أبجدي ي-أ' : 'Z-A') :
                       sortBy === 'date_desc' ? (isRTL ? 'الأحدث أولاً' : 'Newest') :
                       sortBy === 'date_asc' ? (isRTL ? 'الأقدم أولاً' : 'Oldest') :
                       sortBy === 'number_asc' ? (isRTL ? 'رقم الطالب ↑' : 'Number ↑') :
                       sortBy === 'grade_asc' ? (isRTL ? 'المرحلة ↑' : 'Grade ↑') :
                       sortBy === 'capacity_desc' ? (isRTL ? 'الأكثر طلاباً' : 'Most Students') :
                       (isRTL ? 'ترتيب' : 'Sort')}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem onClick={() => setSortBy('name_asc')} className={sortBy === 'name_asc' ? 'bg-accent' : ''}>
                    <ArrowUp className="h-3.5 w-3.5 me-2" />{isRTL ? 'أبجدي أ → ي' : 'Alphabetical A → Z'}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setSortBy('name_desc')} className={sortBy === 'name_desc' ? 'bg-accent' : ''}>
                    <ArrowDown className="h-3.5 w-3.5 me-2" />{isRTL ? 'أبجدي ي → أ' : 'Alphabetical Z → A'}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => setSortBy('date_desc')} className={sortBy === 'date_desc' ? 'bg-accent' : ''}>
                    <Clock className="h-3.5 w-3.5 me-2" />{isRTL ? 'الأحدث أولاً' : 'Newest First'}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setSortBy('date_asc')} className={sortBy === 'date_asc' ? 'bg-accent' : ''}>
                    <Clock className="h-3.5 w-3.5 me-2" />{isRTL ? 'الأقدم أولاً' : 'Oldest First'}
                  </DropdownMenuItem>
                  {activeTab === 'students' && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => setSortBy('number_asc')} className={sortBy === 'number_asc' ? 'bg-accent' : ''}>
                        <Hash className="h-3.5 w-3.5 me-2" />{isRTL ? 'رقم الطالب' : 'Student Number'}
                      </DropdownMenuItem>
                    </>
                  )}
                  {activeTab === 'classes' && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => setSortBy('grade_asc')} className={sortBy === 'grade_asc' ? 'bg-accent' : ''}>
                        <GraduationCap className="h-3.5 w-3.5 me-2" />{isRTL ? 'حسب المرحلة' : 'By Grade Level'}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setSortBy('capacity_desc')} className={sortBy === 'capacity_desc' ? 'bg-accent' : ''}>
                        <Users className="h-3.5 w-3.5 me-2" />{isRTL ? 'الأكثر طلاباً' : 'Most Students'}
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              <div className="flex items-center bg-muted/50 rounded-lg p-0.5">
                <Button variant={viewMode === 'grid' ? 'default' : 'ghost'} size="icon" className="h-8 w-8 rounded-md"
                  onClick={() => setViewMode('grid')} title={isRTL ? 'عرض شبكي' : 'Grid View'}>
                  <LayoutGrid className="h-4 w-4" />
                </Button>
                <Button variant={viewMode === 'list' ? 'default' : 'ghost'} size="icon" className="h-8 w-8 rounded-md"
                  onClick={() => setViewMode('list')} title={isRTL ? 'عرض قائمة' : 'List View'}>
                  <List className="h-4 w-4" />
                </Button>
              </div>
              <div className="relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input placeholder={isRTL ? 'بحث...' : 'Search...'} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                  className="ps-10 w-[200px] lg:w-[280px] rounded-xl h-10" data-testid="search-input" />
              </div>
              <Button variant="outline" size="icon" onClick={handleRefresh} className="rounded-xl h-10 w-10" title={isRTL ? 'تحديث' : 'Refresh'}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {activeFilter && (
            <div className="flex items-center gap-2 p-2.5 px-4 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800">
              <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
              <span className="text-sm text-amber-700 dark:text-amber-300 flex-1">
                {activeFilter === 'noParent' ? (isRTL ? 'عرض الطلاب بدون ولي أمر' : 'Showing students without a parent') :
                 activeFilter === 'noClass' ? (isRTL ? 'عرض الطلاب بدون فصل' : 'Showing students without a class') :
                 activeFilter === 'noSubject' ? (isRTL ? 'عرض المعلمين بدون مادة' : 'Showing teachers without a subject') :
                 activeFilter === 'noEmail' ? (isRTL ? 'عرض الحسابات بدون بريد' : 'Showing accounts without email') :
                 activeFilter === 'suspended' ? (isRTL ? 'عرض الحسابات المعلقة' : 'Showing suspended accounts') :
                 activeFilter === 'overCapacity' ? (isRTL ? 'عرض الفصول التي تجاوزت السعة' : 'Showing over-capacity classes') : ''}
              </span>
              <Button variant="ghost" size="sm" onClick={clearFilter} className="h-7 text-xs text-amber-700 hover:text-amber-900">
                <X className="h-3.5 w-3.5 me-1" />{isRTL ? 'إزالة الفلتر' : 'Clear Filter'}
              </Button>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
              <span className="ms-3 text-muted-foreground">{isRTL ? 'جاري التحميل...' : 'Loading...'}</span>
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
                      <TabsTrigger value="import"><FileUp className="h-4 w-4 me-2" />{isRTL ? 'استيراد' : 'Import'}</TabsTrigger>
                      <TabsTrigger value="export"><FileDown className="h-4 w-4 me-2" />{isRTL ? 'تصدير' : 'Export'}</TabsTrigger>
                    </TabsList>

                    <TabsContent value="import">
                      <div className="grid gap-6 lg:grid-cols-2">
                        <Card>
                          <CardHeader>
                            <CardTitle className="flex items-center gap-2"><Upload className="h-5 w-5 text-brand-turquoise" />{isRTL ? 'استيراد البيانات' : 'Import Data'}</CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-5">
                            <div className="space-y-2">
                              <Label className="text-sm">{isRTL ? 'نوع البيانات' : 'Data Type'}</Label>
                              <div className="grid grid-cols-2 gap-3">
                                {[{ value: 'students', label: isRTL ? 'الطلاب' : 'Students', icon: GraduationCap }, { value: 'teachers', label: isRTL ? 'المعلمين' : 'Teachers', icon: Users }].map(opt => {
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
                            <Button variant="outline" onClick={() => downloadTemplate(importType)} disabled={downloadingTemplate} className="w-full">{downloadingTemplate ? <Loader2 className="h-4 w-4 me-2 animate-spin" /> : <Download className="h-4 w-4 me-2" />}{downloadingTemplate ? (isRTL ? 'جاري التحميل...' : 'Downloading...') : (isRTL ? 'تحميل القالب' : 'Download Template')}</Button>
                            <div className="border-2 border-dashed rounded-xl p-5 text-center hover:border-brand-turquoise/50 transition-colors">
                              <Input type="file" accept=".xlsx,.xls,.csv" onChange={handleFileSelect} className="hidden" id="file-upload" />
                              <label htmlFor="file-upload" className="cursor-pointer">
                                <FileSpreadsheet className="h-10 w-10 mx-auto mb-2 text-muted-foreground" />
                                <p className="text-xs text-muted-foreground">{isRTL ? 'اسحب أو اختر ملف' : 'Drag or select file'}</p>
                              </label>
                              {selectedFile && <Badge variant="outline" className="mt-2">{selectedFile.name}</Badge>}
                            </div>
                            <Button onClick={handleImport} disabled={importing || !selectedFile} className="w-full">
                              {importing ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Upload className="h-4 w-4 me-2" />}
                              {importing ? (isRTL ? 'جاري الاستيراد...' : 'Importing...') : (isRTL ? 'بدء الاستيراد' : 'Start Import')}
                            </Button>
                          </CardContent>
                        </Card>
                        {importResult && (
                          <Card>
                            <CardHeader><CardTitle>{isRTL ? 'نتيجة الاستيراد' : 'Import Result'}</CardTitle></CardHeader>
                            <CardContent className="space-y-3">
                              <div className="grid grid-cols-3 gap-3 text-center">
                                <div className="p-3 bg-muted/50 rounded-lg"><p className="text-xl font-bold">{importResult.total_rows || 0}</p><p className="text-xs text-muted-foreground">{isRTL ? 'إجمالي' : 'Total'}</p></div>
                                <div className="p-3 bg-green-50 dark:bg-green-950/30 rounded-lg"><p className="text-xl font-bold text-green-600">{importResult.imported || 0}</p><p className="text-xs text-muted-foreground">{isRTL ? 'نجح' : 'Done'}</p></div>
                                <div className="p-3 bg-red-50 dark:bg-red-950/30 rounded-lg"><p className="text-xl font-bold text-red-600">{importResult.failed || 0}</p><p className="text-xs text-muted-foreground">{isRTL ? 'فشل' : 'Failed'}</p></div>
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
                        <CardHeader><CardTitle className="flex items-center gap-2"><Download className="h-5 w-5 text-brand-turquoise" />{isRTL ? 'تصدير البيانات' : 'Export Data'}</CardTitle></CardHeader>
                        <CardContent className="space-y-4">
                          <div className="space-y-2">
                            <Label>{isRTL ? 'نوع البيانات' : 'Data Type'}</Label>
                            <Select value={exportType} onValueChange={setExportType}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="students">{isRTL ? 'الطلاب' : 'Students'}</SelectItem>
                                <SelectItem value="teachers">{isRTL ? 'المعلمين' : 'Teachers'}</SelectItem>
                                <SelectItem value="schedule">{isRTL ? 'الجدول' : 'Schedule'}</SelectItem>
                                <SelectItem value="attendance">{isRTL ? 'الحضور' : 'Attendance'}</SelectItem>
                                <SelectItem value="grades">{isRTL ? 'الدرجات' : 'Grades'}</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <Label>{isRTL ? 'الصيغة' : 'Format'}</Label>
                            <div className="flex gap-2">
                              {['xlsx', 'csv', 'json'].map(f => (
                                <Button key={f} variant={exportFormat === f ? 'default' : 'outline'} size="sm" onClick={() => setExportFormat(f)} className="flex-1">{f.toUpperCase()}</Button>
                              ))}
                            </div>
                          </div>
                          <Button onClick={handleExport} disabled={exporting} className="w-full">
                            {exporting ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Download className="h-4 w-4 me-2" />}
                            {exporting ? (isRTL ? 'جاري التصدير...' : 'Exporting...') : (isRTL ? 'تصدير' : 'Export')}
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
                {selectedItemType === 'teacher' ? (isRTL ? 'تفاصيل المعلم' : 'Teacher Details') :
                 selectedItemType === 'parent' ? (isRTL ? 'تفاصيل ولي الأمر' : 'Parent Details') :
                 (isRTL ? 'تفاصيل الفصل' : 'Class Details')}
              </DialogTitle>
            </DialogHeader>
            {selectedItem && selectedItemType === 'teacher' && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <TeacherAvatar teacher={selectedItem} size="lg" />
                  <div>
                    <h3 className="font-bold text-lg">{selectedItem.full_name}</h3>
                    <p className="text-sm text-muted-foreground">{selectedItem.specialization || (isRTL ? 'معلم' : 'Teacher')}</p>
                    <Badge className="mt-1">{selectedItem.rank || (isRTL ? 'معلم' : 'Teacher')}</Badge>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><span className="text-muted-foreground">{isRTL ? 'البريد' : 'Email'}:</span> <span className="font-medium">{selectedItem.email || '-'}</span></div>
                  <div><span className="text-muted-foreground">{isRTL ? 'الهاتف' : 'Phone'}:</span> <span className="font-medium">{selectedItem.phone || '-'}</span></div>
                  <div><span className="text-muted-foreground">{isRTL ? 'الخبرة' : 'Experience'}:</span> <span className="font-medium">{selectedItem.years_of_experience || 0} {isRTL ? 'سنة' : 'years'}</span></div>
                  <div><span className="text-muted-foreground">{isRTL ? 'الحالة' : 'Status'}:</span>
                    <Badge variant={selectedItem.is_active !== false ? 'default' : 'secondary'} className="ms-1">{selectedItem.is_active !== false ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}</Badge>
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
                    <p className="text-sm text-muted-foreground">{selectedItem.relationship || (isRTL ? 'ولي أمر' : 'Parent')}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><span className="text-muted-foreground">{isRTL ? 'الهاتف' : 'Phone'}:</span> <span className="font-medium" dir="ltr">{selectedItem.phone || '-'}</span></div>
                  <div><span className="text-muted-foreground">{isRTL ? 'البريد' : 'Email'}:</span> <span className="font-medium">{selectedItem.email || '-'}</span></div>
                  <div><span className="text-muted-foreground">{isRTL ? 'الهوية' : 'National ID'}:</span> <span className="font-medium">{selectedItem.national_id || '-'}</span></div>
                  <div><span className="text-muted-foreground">{isRTL ? 'عدد الأبناء' : 'Children'}:</span> <span className="font-medium">{selectedItem.children_count || 0}</span></div>
                </div>
                {selectedItem.children?.length > 0 && (
                  <div>
                    <p className="text-sm font-semibold mb-2">{isRTL ? 'الأبناء المسجلون' : 'Registered Children'}</p>
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
                      <Edit className="h-3.5 w-3.5 me-1" />{isRTL ? 'تعديل' : 'Edit'}
                    </Button>
                  )}
                </div>

                {viewClassEditing ? (
                  <div className="space-y-3 border rounded-lg p-3">
                    <div className="space-y-2">
                      <Label>{isRTL ? 'اسم الفصل' : 'Class Name'}</Label>
                      <Input value={viewClassForm.name} onChange={(e) => setViewClassForm({ ...viewClassForm, name: e.target.value })} />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <Label>{isRTL ? 'الصف' : 'Grade'}</Label>
                        <Input value={viewClassForm.grade_level} onChange={(e) => setViewClassForm({ ...viewClassForm, grade_level: e.target.value })} />
                      </div>
                      <div className="space-y-2">
                        <Label>{isRTL ? 'الشعبة' : 'Section'}</Label>
                        <Input value={viewClassForm.section} onChange={(e) => setViewClassForm({ ...viewClassForm, section: e.target.value })} />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'السعة' : 'Capacity'}</Label>
                      <Input type="number" value={viewClassForm.capacity} onChange={(e) => setViewClassForm({ ...viewClassForm, capacity: parseInt(e.target.value) || 30 })} />
                    </div>
                    <div className="flex gap-2 justify-end">
                      <Button size="sm" variant="outline" onClick={() => setViewClassEditing(false)}><X className="h-3.5 w-3.5 me-1" />{isRTL ? 'إلغاء' : 'Cancel'}</Button>
                      <Button size="sm" disabled={viewClassSaving} onClick={async () => {
                        setViewClassSaving(true);
                        try {
                          const updateData = {};
                          if (viewClassForm.name) updateData.name = viewClassForm.name;
                          if (viewClassForm.grade_level) updateData.grade_level = viewClassForm.grade_level;
                          if (viewClassForm.section) updateData.section = viewClassForm.section;
                          if (viewClassForm.capacity) updateData.capacity = viewClassForm.capacity;
                          await api.put(`/classes/${selectedItem.id}`, updateData);
                          toast.success(isRTL ? 'تم حفظ التعديلات' : 'Changes saved');
                          setViewClassEditing(false);
                          fetchAllData();
                          setViewDialogOpen(false);
                        } catch (e) {
                          nassaqError(e.response?.data?.detail || (isRTL ? 'فشل الحفظ' : 'Save failed'));
                        } finally { setViewClassSaving(false); }
                      }}>
                        {viewClassSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Save className="h-3.5 w-3.5 me-1" />}
                        {isRTL ? 'حفظ' : 'Save'}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div><span className="text-muted-foreground">{isRTL ? 'السعة' : 'Capacity'}:</span> <span className="font-medium">{selectedItem.student_count || 0} / {selectedItem.capacity || 30}</span></div>
                      <div><span className="text-muted-foreground">{isRTL ? 'معلم الفصل' : 'Homeroom'}:</span> <span className="font-medium">{selectedItem.homeroom_teacher_name || '-'}</span></div>
                    </div>
                    <Progress value={((selectedItem.student_count || 0) / (selectedItem.capacity || 30)) * 100} className="h-2" />
                  </>
                )}

                <div className="border-t pt-3">
                  <h4 className="font-semibold text-sm text-red-600 mb-2">{isRTL ? 'منطقة الخطر' : 'Danger Zone'}</h4>
                  <Button
                    variant="outline"
                    className="justify-start h-auto py-3 border-red-200 hover:bg-red-50 w-full"
                    disabled={viewClassSaving}
                    onClick={() => {
                      nassaqConfirm(
                        isRTL ? 'هل أنت متأكد من حذف هذا الفصل نهائياً؟ لا يمكن التراجع عن هذا الإجراء.' : 'Are you sure you want to permanently delete this class? This action cannot be undone.',
                        async () => {
                          setViewClassSaving(true);
                          try {
                            await api.delete(`/classes/${selectedItem.id}`);
                            toast.success(isRTL ? 'تم حذف الفصل بنجاح' : 'Class deleted successfully');
                            setViewDialogOpen(false);
                            fetchAllData();
                          } catch (e) {
                            nassaqError(e.response?.data?.detail || (isRTL ? 'فشل حذف الفصل' : 'Failed to delete class'));
                          } finally { setViewClassSaving(false); }
                        },
                        { title: isRTL ? 'تأكيد الحذف النهائي' : 'Confirm Permanent Delete', confirmText: isRTL ? 'نعم، احذف نهائياً' : 'Yes, Delete Permanently', cancelText: isRTL ? 'إلغاء' : 'Cancel' }
                      );
                    }}
                  >
                    <Trash2 className="h-4 w-4 me-2 text-red-500" />
                    <div className="text-start">
                      <p className="text-sm font-medium text-red-600">{isRTL ? 'حذف الفصل نهائياً' : 'Delete Class Permanently'}</p>
                      <p className="text-xs text-muted-foreground">{isRTL ? 'لا يمكن التراجع عن هذا الإجراء' : 'This action cannot be undone'}</p>
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
              <DialogTitle>{isRTL ? 'تعديل البيانات' : 'Edit Details'}</DialogTitle>
            </DialogHeader>
            {selectedItem && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{isRTL ? 'الاسم' : 'Name'}</Label>
                  <Input value={editFormData.full_name || editFormData.name || ''} onChange={(e) => setEditFormData({ ...editFormData, full_name: e.target.value, name: e.target.value })} />
                </div>
                {selectedItemType !== 'class' && (
                  <>
                    <div className="space-y-2"><Label>{isRTL ? 'البريد الإلكتروني' : 'Email'}</Label><Input value={editFormData.email || ''} onChange={(e) => setEditFormData({ ...editFormData, email: e.target.value })} /></div>
                    <div className="space-y-2"><Label>{isRTL ? 'الهاتف' : 'Phone'}</Label><Input value={editFormData.phone || ''} onChange={(e) => setEditFormData({ ...editFormData, phone: e.target.value })} /></div>
                  </>
                )}
                {selectedItemType === 'student' && (
                  <>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'الفصل' : 'Class'}</Label>
                      <Select value={editFormData.class_id || ''} onValueChange={(v) => setEditFormData({ ...editFormData, class_id: v })}>
                        <SelectTrigger><SelectValue placeholder={isRTL ? 'اختر فصل' : 'Select class'} /></SelectTrigger>
                        <SelectContent>{classes.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl border border-amber-200/60 bg-amber-50/50 dark:bg-amber-950/20 dark:border-amber-800/40">
                      <div className="flex items-center gap-2">
                        <Star className={`h-4 w-4 ${editFormData.is_gifted ? 'text-amber-500 fill-amber-500' : 'text-muted-foreground'}`} />
                        <Label className="cursor-pointer">{isRTL ? 'طالب موهوب' : 'Gifted Student'}</Label>
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
                  <div className="space-y-2"><Label>{isRTL ? 'التخصص' : 'Specialization'}</Label><Input value={editFormData.specialization || ''} onChange={(e) => setEditFormData({ ...editFormData, specialization: e.target.value })} /></div>
                )}
                {selectedItemType === 'class' && (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2"><Label>{isRTL ? 'الصف' : 'Grade'}</Label><Input value={editFormData.grade_level || editFormData.grade || ''} onChange={(e) => setEditFormData({ ...editFormData, grade_level: e.target.value })} /></div>
                      <div className="space-y-2"><Label>{isRTL ? 'الشعبة' : 'Section'}</Label><Input value={editFormData.section || ''} onChange={(e) => setEditFormData({ ...editFormData, section: e.target.value })} /></div>
                    </div>
                    <div className="space-y-2"><Label>{isRTL ? 'السعة' : 'Capacity'}</Label><Input type="number" value={editFormData.capacity || ''} onChange={(e) => setEditFormData({ ...editFormData, capacity: parseInt(e.target.value) || 30 })} /></div>
                  </>
                )}
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditDialogOpen(false)}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              <Button onClick={handleSaveEdit} disabled={editLoading}>
                {editLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Save className="h-4 w-4 me-2" />}
                {isRTL ? 'حفظ' : 'Save'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}
