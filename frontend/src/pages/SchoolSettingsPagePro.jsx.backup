/**
 * صفحة إعدادات المدرسة - التصميم الاحترافي الشامل
 * تعرض جميع البيانات من قاعدة البيانات مع إمكانية التعديل والحذف والإضافة
 * 
 * الأقسام الرئيسية:
 * 1. أيام العمل والعطلات
 * 2. التوزيع الزمني الكامل (الفترات، الاستراحات، الصلاة)
 * 3. بيانات المعلمين
 * 4. بيانات الفصول
 * 5. المواد الدراسية
 * 6. رتب المعلمين والنصاب التدريسي
 * 7. القيود الإدارية
 * 8. الهيكل الأكاديمي
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { toast } from 'sonner';

// Shadcn UI Components
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { Progress } from '../components/ui/progress';

// Icons
import {
  Settings, Globe, Sun, Moon, RefreshCw, Save, Edit2, Plus, Trash2, X,
  Calendar, Clock, Users, BookOpen, GraduationCap, Shield, Target,
  ChevronRight, ChevronDown, ChevronLeft, Building2, MapPin, Phone, Mail,
  Grid3X3, Coffee, Play, CheckCircle2, AlertTriangle, Info, Eye, EyeOff,
  CalendarDays, Timer, Loader2, FileText, Copy, Check, School, Layers,
  AlertCircle, Ban, Star, Award, Bookmark, ArrowRight, ArrowUpDown, Filter,
  ToggleLeft, ToggleRight
} from 'lucide-react';
import { NotificationBell } from '../components/notifications/NotificationBell';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ============================================
// الثوابت
// ============================================
const DAYS_AR = {
  sunday: 'الأحد',
  monday: 'الإثنين',
  tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء',
  thursday: 'الخميس',
  friday: 'الجمعة',
  saturday: 'السبت'
};

const CATEGORY_COLORS = {
  language: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300', icon: 'text-blue-600' },
  science: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300', icon: 'text-green-600' },
  islamic: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', icon: 'text-emerald-600' },
  activity: { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-300', icon: 'text-orange-600' },
  social: { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-300', icon: 'text-purple-600' },
  technology: { bg: 'bg-cyan-100', text: 'text-cyan-700', border: 'border-cyan-300', icon: 'text-cyan-600' },
  skills: { bg: 'bg-pink-100', text: 'text-pink-700', border: 'border-pink-300', icon: 'text-pink-600' },
  default: { bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-300', icon: 'text-gray-600' },
};

// ============================================
// مكون كارت الإحصائيات
// ============================================
const StatCard = ({ title, value, icon: Icon, color, trend, onClick }) => (
  <Card 
    className={`border-2 ${color} cursor-pointer hover:shadow-lg transition-all duration-300 transform hover:scale-[1.02]`}
    onClick={onClick}
    data-testid={`stat-card-${title}`}
  >
    <CardContent className="p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl bg-opacity-20 flex items-center justify-center ${color.replace('border-', 'bg-').replace('-200', '-100')}`}>
            <Icon className={`h-6 w-6 ${color.replace('border-', 'text-').replace('-200', '-600')}`} />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
          </div>
        </div>
        {trend && (
          <Badge variant="secondary" className="text-xs">
            {trend}
          </Badge>
        )}
      </div>
    </CardContent>
  </Card>
);

// ============================================
// مكون عرض الأيام التفاعلي
// ============================================
const DaysGrid = ({ workDays = [], weekendDays = [], onToggle, editable = false }) => {
  const allDays = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
  
  return (
    <div className="grid grid-cols-7 gap-2">
      {allDays.map((day) => {
        const isWorkDay = workDays.includes(DAYS_AR[day]) || workDays.includes(day);
        const isWeekend = weekendDays.includes(DAYS_AR[day]) || weekendDays.includes(day);
        
        return (
          <div
            key={day}
            onClick={() => editable && onToggle?.(day)}
            className={`
              p-3 rounded-xl text-center transition-all duration-200
              ${editable ? 'cursor-pointer hover:scale-105' : ''}
              ${isWorkDay 
                ? 'bg-gradient-to-br from-green-100 to-green-50 border-2 border-green-400 text-green-800 shadow-sm' 
                : isWeekend
                  ? 'bg-gradient-to-br from-red-100 to-red-50 border-2 border-red-300 text-red-700'
                  : 'bg-gray-100 border-2 border-gray-200 text-gray-500'
              }
            `}
          >
            <p className="font-bold text-sm">{DAYS_AR[day]}</p>
            <p className="text-[10px] mt-1 opacity-80">
              {isWorkDay ? 'دراسة' : 'عطلة'}
            </p>
            {isWorkDay && (
              <CheckCircle2 className="h-3 w-3 mx-auto mt-1 text-green-600" />
            )}
          </div>
        );
      })}
    </div>
  );
};

// ============================================
// مكون عرض الفترة الزمنية مع التعديل المباشر (Inline Edit)
// ============================================
const TimeSlotInlineEdit = ({ slot, index, allSlots, onTimeChange, onSave, isSaving }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedStartTime, setEditedStartTime] = useState(slot.start_time);
  const [error, setError] = useState('');
  
  const getSlotStyle = (type) => {
    switch(type) {
      case 'break': return 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-300 text-amber-800';
      case 'prayer': return 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-300 text-green-800';
      default: return 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-300 text-blue-800';
    }
  };
  
  const getSlotIcon = (type) => {
    switch(type) {
      case 'break': return <Coffee className="h-4 w-4" />;
      case 'prayer': return <Moon className="h-4 w-4" />;
      default: return <BookOpen className="h-4 w-4" />;
    }
  };

  const getSlotLabel = (type) => {
    switch(type) {
      case 'break': return 'استراحة';
      case 'prayer': return 'صلاة';
      default: return 'حصة';
    }
  };
  
  // Validate time format and logic
  const validateTime = (newStartTime) => {
    if (!newStartTime || !/^\d{2}:\d{2}$/.test(newStartTime)) {
      return 'صيغة الوقت غير صحيحة';
    }
    
    // Check if start time is after previous slot's end time
    if (index > 0) {
      const prevSlot = allSlots[index - 1];
      if (prevSlot && newStartTime < prevSlot.end_time) {
        return `يجب أن يبدأ بعد ${prevSlot.end_time}`;
      }
    }
    
    return '';
  };
  
  // Handle blur/enter to save
  const handleSave = () => {
    const validationError = validateTime(editedStartTime);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError('');
    setIsEditing(false);
    onTimeChange(index, editedStartTime);
  };
  
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      setEditedStartTime(slot.start_time);
      setIsEditing(false);
      setError('');
    }
  };
  
  return (
    <div className={`flex items-center justify-between p-4 rounded-xl border-2 ${getSlotStyle(slot.type || 'period')} hover:shadow-md transition-all group relative`}>
      {/* Saving indicator */}
      {isSaving && (
        <div className="absolute top-2 left-2">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
        </div>
      )}
      
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-white shadow-sm">
          {slot.type === 'period' ? (
            <span className="font-bold text-lg text-blue-600">{slot.slot_number || index + 1}</span>
          ) : (
            getSlotIcon(slot.type)
          )}
        </div>
        <div>
          <p className="font-bold text-base">{slot.name_ar || slot.name}</p>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline" className="text-xs">
              {slot.duration || slot.duration_minutes} دقيقة
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {getSlotLabel(slot.type)}
            </Badge>
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-3">
        <div className="text-left bg-white px-3 py-2 rounded-lg shadow-sm min-w-[180px]">
          <p className="text-xs text-muted-foreground mb-1">من - إلى</p>
          {isEditing ? (
            <div className="flex items-center gap-2">
              <Input
                type="time"
                value={editedStartTime}
                onChange={(e) => setEditedStartTime(e.target.value)}
                onBlur={handleSave}
                onKeyDown={handleKeyDown}
                className={`w-24 h-8 text-center font-mono font-bold ${error ? 'border-red-500' : ''}`}
                autoFocus
                data-testid={`time-slot-${index}-start`}
              />
              <span className="text-muted-foreground">-</span>
              <span className="font-mono font-bold text-muted-foreground">{slot.end_time}</span>
            </div>
          ) : (
            <div 
              className="font-mono font-bold text-lg cursor-pointer hover:text-blue-600 transition-colors flex items-center gap-1"
              onClick={() => setIsEditing(true)}
              title="انقر للتعديل المباشر"
            >
              <Edit2 className="h-3 w-3 opacity-0 group-hover:opacity-50" />
              {slot.start_time} <span className="text-muted-foreground mx-1">-</span> {slot.end_time}
            </div>
          )}
          {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
        </div>
      </div>
    </div>
  );
};

// Legacy component for backward compatibility
const TimeSlotItem = ({ slot, index, onEdit, onDelete }) => {
  const getSlotStyle = (type) => {
    switch(type) {
      case 'break': return 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-300 text-amber-800';
      case 'prayer': return 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-300 text-green-800';
      default: return 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-300 text-blue-800';
    }
  };
  
  const getSlotIcon = (type) => {
    switch(type) {
      case 'break': return <Coffee className="h-4 w-4" />;
      case 'prayer': return <Moon className="h-4 w-4" />;
      default: return <BookOpen className="h-4 w-4" />;
    }
  };

  const getSlotLabel = (type) => {
    switch(type) {
      case 'break': return 'استراحة';
      case 'prayer': return 'صلاة';
      default: return 'حصة';
    }
  };
  
  return (
    <div className={`flex items-center justify-between p-4 rounded-xl border-2 ${getSlotStyle(slot.type || 'period')} hover:shadow-md transition-all group`}>
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-white shadow-sm">
          {slot.type === 'period' ? (
            <span className="font-bold text-lg text-blue-600">{slot.slot_number || index + 1}</span>
          ) : (
            getSlotIcon(slot.type)
          )}
        </div>
        <div>
          <p className="font-bold text-base">{slot.name_ar || slot.name}</p>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline" className="text-xs">
              {slot.duration || slot.duration_minutes} دقيقة
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {getSlotLabel(slot.type)}
            </Badge>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-left bg-white px-4 py-2 rounded-lg shadow-sm">
          <p className="text-xs text-muted-foreground">من - إلى</p>
          <p className="font-mono font-bold text-lg">
            {slot.start_time} <span className="text-muted-foreground">-</span> {slot.end_time}
          </p>
        </div>
        {(onEdit || onDelete) && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {onEdit && (
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => onEdit(slot)}>
                <Edit2 className="h-4 w-4" />
              </Button>
            )}
            {onDelete && (
              <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500 hover:text-red-700" onClick={() => onDelete(slot)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================
// مكون كارت المعلم
// ============================================
const TeacherItem = ({ teacher }) => (
  <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-violet-50 to-purple-50 border-2 border-violet-200 hover:shadow-lg hover:border-violet-300 transition-all group">
    <div className="flex items-center gap-4">
      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
        <span className="text-white font-bold text-lg">
          {(teacher.full_name || teacher.full_name_ar || 'م')?.charAt(0)}
        </span>
      </div>
      <div>
        <p className="font-bold text-violet-900">{teacher.full_name || teacher.full_name_ar}</p>
        <div className="flex items-center gap-2 mt-1">
          <Badge className="bg-violet-100 text-violet-700 border-violet-300 text-xs">
            {teacher.subject_name || teacher.specialization || 'غير محدد'}
          </Badge>
          <Badge variant="outline" className="text-xs">
            {teacher.rank_name_ar || teacher.rank_name || 'معلم'}
          </Badge>
        </div>
      </div>
    </div>
    <div className="flex items-center gap-4">
      <div className="text-center bg-white px-4 py-2 rounded-lg shadow-sm">
        <p className="text-2xl font-bold text-violet-600">{teacher.weekly_periods || 24}</p>
        <p className="text-xs text-muted-foreground">حصة/أسبوع</p>
      </div>
    </div>
  </div>
);

// ============================================
// مكون كارت الفصل
// ============================================
const ClassItem = ({ classItem }) => (
  <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-cyan-50 to-teal-50 border-2 border-cyan-200 hover:shadow-lg hover:border-cyan-300 transition-all group">
    <div className="flex items-center gap-4">
      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center shadow-lg">
        <GraduationCap className="h-6 w-6 text-white" />
      </div>
      <div>
        <p className="font-bold text-cyan-900">{classItem.name || classItem.name_ar}</p>
        <div className="flex items-center gap-2 mt-1">
          <Badge className="bg-cyan-100 text-cyan-700 border-cyan-300 text-xs">
            {classItem.grade_name_ar || classItem.grade_name || 'غير محدد'}
          </Badge>
          {classItem.section && (
            <Badge variant="outline" className="text-xs">
              شعبة {classItem.section}
            </Badge>
          )}
        </div>
      </div>
    </div>
    <div className="flex items-center gap-4">
      <div className="text-center bg-white px-4 py-2 rounded-lg shadow-sm">
        <p className="text-2xl font-bold text-cyan-600">{classItem.current_students || classItem.student_count || 0}</p>
        <p className="text-xs text-muted-foreground">طالب</p>
      </div>
    </div>
  </div>
);

// ============================================
// مكون كارت المادة
// ============================================
const SubjectItem = ({ subject, onEdit, onDelete }) => {
  const colors = CATEGORY_COLORS[subject.category] || CATEGORY_COLORS.default;
  
  return (
    <div className={`flex items-center justify-between p-3 rounded-xl ${colors.bg} border-2 ${colors.border} hover:shadow-md transition-all group`}>
      <div className="flex items-center gap-3">
        <BookOpen className={`h-5 w-5 ${colors.icon}`} />
        <div>
          <p className={`font-bold text-sm ${colors.text}`}>{subject.name_ar}</p>
          <p className="text-xs text-muted-foreground">{subject.name_en}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="secondary" className="text-xs font-bold">
          {subject.weekly_periods} ح/أسبوع
        </Badge>
        {(onEdit || onDelete) && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {onEdit && (
              <Button variant="ghost" size="icon" className="h-6 w-6 text-blue-500" onClick={onEdit}>
                <Edit2 className="h-3 w-3" />
              </Button>
            )}
            {onDelete && (
              <Button variant="ghost" size="icon" className="h-6 w-6 text-red-500" onClick={onDelete}>
                <Trash2 className="h-3 w-3" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================
// مكون كارت رتبة المعلم
// ============================================
const RankItem = ({ rank }) => (
  <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-teal-50 to-cyan-50 border-2 border-teal-200 hover:shadow-md transition-all">
    <div className="flex items-center gap-4">
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center shadow-md">
        <Award className="h-5 w-5 text-white" />
      </div>
      <div>
        <p className="font-bold text-teal-800">{rank.name_ar}</p>
        <p className="text-xs text-muted-foreground">{rank.name_en}</p>
      </div>
    </div>
    <div className="flex items-center gap-3">
      <div className="text-center bg-white px-3 py-2 rounded-lg shadow-sm">
        <p className="text-xl font-bold text-teal-600">{rank.weekly_periods}</p>
        <p className="text-[10px] text-muted-foreground">حصة/أسبوع</p>
      </div>
      <div className="text-center bg-white px-3 py-2 rounded-lg shadow-sm">
        <p className="text-xl font-bold text-cyan-600">{rank.daily_max}</p>
        <p className="text-[10px] text-muted-foreground">حد يومي</p>
      </div>
      {rank.is_special_education && (
        <Badge className="bg-purple-100 text-purple-700">تربية خاصة</Badge>
      )}
    </div>
  </div>
);

// ============================================
// مكون كارت القيد الإداري مع زر التفعيل
// ============================================
const ConstraintItem = ({ constraint, index, onToggle, onEdit, onDelete }) => {
  const getPriorityStyle = (priority) => {
    switch(priority) {
      case 'critical': return 'bg-red-100 text-red-700 border-red-300';
      case 'high': return 'bg-orange-100 text-orange-700 border-orange-300';
      case 'medium': return 'bg-yellow-100 text-yellow-700 border-yellow-300';
      default: return 'bg-gray-100 text-gray-700 border-gray-300';
    }
  };

  const getPriorityLabel = (priority) => {
    switch(priority) {
      case 'critical': return 'حرج';
      case 'high': return 'عالي';
      case 'medium': return 'متوسط';
      default: return 'عادي';
    }
  };

  return (
    <div className="flex items-start gap-4 p-4 rounded-xl bg-gradient-to-r from-rose-50 to-pink-50 border-2 border-rose-200 hover:shadow-md transition-all group">
      <div className="w-8 h-8 rounded-full bg-rose-200 flex items-center justify-center flex-shrink-0">
        <span className="text-sm font-bold text-rose-700">{index + 1}</span>
      </div>
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <p className="font-bold text-rose-800">{constraint.name_ar}</p>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={`text-xs ${getPriorityStyle(constraint.priority)}`}>
              {getPriorityLabel(constraint.priority)}
            </Badge>
            <Button
              variant={constraint.is_active ? "default" : "outline"}
              size="sm"
              className={`text-xs h-7 ${constraint.is_active ? 'bg-green-600 hover:bg-green-700' : ''}`}
              onClick={() => onToggle?.(constraint)}
              data-testid={`toggle-constraint-${constraint.id}`}
            >
              {constraint.is_active ? (
                <>
                  <CheckCircle2 className="h-3 w-3 ml-1" /> مفعّل
                </>
              ) : (
                <>
                  <Ban className="h-3 w-3 ml-1" /> معطّل
                </>
              )}
            </Button>
            {(onEdit || onDelete) && (
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {onEdit && (
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-blue-500" onClick={onEdit}>
                    <Edit2 className="h-3 w-3" />
                  </Button>
                )}
                {onDelete && (
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500" onClick={onDelete}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
        <p className="text-sm text-rose-600 mt-2">{constraint.description_ar}</p>
        {constraint.restricted_periods && constraint.restricted_periods.length > 0 && (
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs text-muted-foreground">الحصص المقيدة:</span>
            {constraint.restricted_periods.map(p => (
              <Badge key={p} variant="secondary" className="text-xs">ح{p}</Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================
// مكون الهيكل الأكاديمي
// ============================================
const AcademicStructureView = ({ 
  stages, 
  grades, 
  tracks, 
  onAddStage, 
  onEditStage, 
  onDeleteStage,
  onAddGrade,
  onEditGrade,
  onDeleteGrade,
  onToggleStage
}) => {
  const [expandedStage, setExpandedStage] = useState(null);

  return (
    <div className="space-y-4">
      {/* Header with Add Stage Button */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <School className="h-5 w-5 text-blue-600" />
          <h3 className="font-bold">المراحل والصفوف</h3>
        </div>
        <Button 
          onClick={onAddStage} 
          className="bg-purple-600 hover:bg-purple-700"
          data-testid="add-stage-btn"
        >
          <Plus className="h-4 w-4 ml-2" />
          إضافة مرحلة
        </Button>
      </div>
      
      {/* معلومات توضيحية */}
      <div className="p-3 bg-blue-50 rounded-lg border border-blue-200 mb-4">
        <p className="text-sm text-blue-700 flex items-center gap-2">
          <Info className="h-4 w-4" />
          المراحل المُفعّلة فقط ستظهر في محرك الجدولة الذكي. يمكنك تعطيل المراحل غير المستخدمة حالياً.
        </p>
      </div>
      
      {stages?.map((stage) => {
        const stageGrades = grades?.filter(g => g.stage_id === stage.id) || [];
        const isExpanded = expandedStage === stage.id;
        const isActive = stage.is_active !== false; // Default to true if undefined
        
        return (
          <Card 
            key={stage.id} 
            className={`border-2 overflow-hidden transition-all ${
              isActive ? 'border-blue-200' : 'border-gray-200 opacity-60'
            }`}
          >
            <CardHeader 
              className={`cursor-pointer transition-colors py-4 ${
                isActive ? 'hover:bg-blue-50/50' : 'bg-gray-50 hover:bg-gray-100'
              }`}
              onClick={() => setExpandedStage(isExpanded ? null : stage.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center shadow-md ${
                    isActive 
                      ? 'bg-gradient-to-br from-blue-500 to-indigo-600' 
                      : 'bg-gradient-to-br from-gray-400 to-gray-500'
                  }`}>
                    <School className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className={`text-base ${!isActive && 'text-gray-500'}`}>
                      {stage.name_ar || stage.name}
                    </CardTitle>
                    <CardDescription className="text-xs">{stage.name_en}</CardDescription>
                  </div>
                  {/* شارة الحالة */}
                  {!isActive && (
                    <Badge className="bg-gray-200 text-gray-600">
                      معطّلة
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <Badge className={isActive ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-500"}>
                    {stageGrades.length} صف
                  </Badge>
                  {/* Stage Actions */}
                  <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                    {/* Toggle Active Button */}
                    <Button
                      variant={isActive ? "default" : "outline"}
                      size="sm"
                      className={`h-8 px-2 ${isActive ? 'bg-green-600 hover:bg-green-700' : 'border-gray-400'}`}
                      onClick={() => onToggleStage && onToggleStage(stage.id, !isActive)}
                      data-testid={`toggle-stage-${stage.id}`}
                      title={isActive ? 'تعطيل المرحلة' : 'تفعيل المرحلة'}
                    >
                      {isActive ? <ToggleRight className="h-4 w-4" /> : <ToggleLeft className="h-4 w-4" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => onEditStage(stage)}
                      data-testid={`edit-stage-${stage.id}`}
                    >
                      <Edit2 className="h-4 w-4 text-blue-600" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => onDeleteStage(stage.id, stage.name_ar || stage.name)}
                      data-testid={`delete-stage-${stage.id}`}
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                  {isExpanded ? <ChevronDown className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
                </div>
              </div>
            </CardHeader>
            {isExpanded && (
              <CardContent className="bg-blue-50/30 border-t">
                <div className="flex justify-between items-center mb-3 pt-3">
                  <h4 className="text-sm font-medium text-muted-foreground">الصفوف الدراسية</h4>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => onAddGrade(stage.id)}
                    data-testid={`add-grade-${stage.id}`}
                  >
                    <Plus className="h-4 w-4 ml-1" />
                    إضافة صف
                  </Button>
                </div>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {stageGrades.map((grade) => (
                    <div key={grade.id} className="flex items-center justify-between p-3 rounded-lg bg-white border border-blue-200 shadow-sm group">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                          <span className="text-sm font-bold text-blue-600">{grade.order}</span>
                        </div>
                        <span className="font-medium text-sm">{grade.name_ar || grade.name}</span>
                      </div>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => onEditGrade(grade)}
                        >
                          <Edit2 className="h-3 w-3 text-blue-600" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => onDeleteGrade(grade.id, grade.name_ar || grade.name)}
                        >
                          <Trash2 className="h-3 w-3 text-red-500" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  {stageGrades.length === 0 && (
                    <div className="col-span-full text-center py-4 text-muted-foreground text-sm">
                      لا توجد صفوف في هذه المرحلة
                    </div>
                  )}
                </div>
              </CardContent>
            )}
          </Card>
        );
      })}
      
      {/* المسارات التعليمية */}
      <Card className="border-2 border-purple-200">
        <CardHeader className="py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center shadow-md">
              <Layers className="h-5 w-5 text-white" />
            </div>
            <div>
              <CardTitle className="text-base">المسارات التعليمية</CardTitle>
              <CardDescription className="text-xs">Education Tracks</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid md:grid-cols-2 gap-3">
            {tracks?.map((track) => (
              <div key={track.id} className="flex items-center justify-between p-3 rounded-lg bg-purple-50 border border-purple-200">
                <div className="flex items-center gap-2">
                  <Bookmark className={`h-5 w-5 ${track.is_quran_track ? 'text-emerald-600' : 'text-purple-600'}`} />
                  <div>
                    <p className="font-medium text-sm">{track.name_ar}</p>
                    <p className="text-xs text-muted-foreground">{track.name_en}</p>
                  </div>
                </div>
                {track.is_quran_track && (
                  <Badge className="bg-emerald-100 text-emerald-700">تحفيظ</Badge>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// ============================================
// الصفحة الرئيسية
// ============================================
export default function SchoolSettingsPagePro() {
  const navigate = useNavigate();
  const { user, api } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  
  // States
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  
  // Edit Mode States
  const [editDayTimesOpen, setEditDayTimesOpen] = useState(false);
  const [editTimeSlotsOpen, setEditTimeSlotsOpen] = useState(false);
  const [editConstraintOpen, setEditConstraintOpen] = useState(false);
  const [selectedConstraint, setSelectedConstraint] = useState(null);
  
  // School Info Edit State
  const [editSchoolInfoOpen, setEditSchoolInfoOpen] = useState(false);
  const [editedSchoolInfo, setEditedSchoolInfo] = useState({});
  
  // Work Days Edit State
  const [editWorkDaysOpen, setEditWorkDaysOpen] = useState(false);
  const [editedWorkDays, setEditedWorkDays] = useState({
    sunday: true, monday: true, tuesday: true, wednesday: true, thursday: true, friday: false, saturday: false
  });
  
  // Stage CRUD States
  const [addStageOpen, setAddStageOpen] = useState(false);
  const [editStageOpen, setEditStageOpen] = useState(false);
  const [editStage, setEditStage] = useState(null);
  const [newStage, setNewStage] = useState({ name: '', name_en: '', order: 1 });
  
  // Grade CRUD States
  const [addGradeOpen, setAddGradeOpen] = useState(false);
  const [editGradeOpen, setEditGradeOpen] = useState(false);
  const [editGrade, setEditGrade] = useState(null);
  const [newGrade, setNewGrade] = useState({ name: '', name_en: '', stage_id: '' });
  
  // Delete Confirmation States
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState({ type: '', id: '', name: '', dependencies: null });
  
  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState([]);
  const [lastSync, setLastSync] = useState(null);
  
  // Timetable Readiness State
  const [readinessData, setReadinessData] = useState(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  
  // Subject CRUD States
  const [addSubjectOpen, setAddSubjectOpen] = useState(false);
  const [editSubjectOpen, setEditSubjectOpen] = useState(false);
  const [editSubject, setEditSubject] = useState(null);
  const [newSubject, setNewSubject] = useState({ name_ar: '', name_en: '', weekly_periods: 4, category: 'general' });
  
  // Constraint CRUD States
  const [addConstraintOpen, setAddConstraintOpen] = useState(false);
  const [editConstraint, setEditConstraint] = useState(null);
  const [newConstraint, setNewConstraint] = useState({ name_ar: '', description_ar: '', priority: 'medium', type: 'hard' });
  
  // Teacher Assignment CRUD States
  const [assignments, setAssignments] = useState([]);
  const [addAssignmentOpen, setAddAssignmentOpen] = useState(false);
  const [editAssignmentOpen, setEditAssignmentOpen] = useState(false);
  const [editAssignment, setEditAssignment] = useState(null);
  const [newAssignment, setNewAssignment] = useState({ teacher_id: '', class_id: '', subject_id: '', weekly_sessions: 4 });
  const [referenceSubjects, setReferenceSubjects] = useState([]);
  
  // Edit Form States
  const [editedDayTimes, setEditedDayTimes] = useState({
    dayStart: '07:00',
    dayEnd: '13:15',
    periodsPerDay: 7,
    periodDuration: 45,
    breakDuration: 20,
    prayerDuration: 20,
  });
  
  // State for auto-calculated time preview
  const [calculatedSlots, setCalculatedSlots] = useState([]);
  const [showCalculatedPreview, setShowCalculatedPreview] = useState(false);
  
  // Function to calculate time slots automatically
  const calculateTimeSlots = (startTime, periodsPerDay, periodDuration, breakDuration, prayerDuration) => {
    const slots = [];
    const [hours, minutes] = startTime.split(':').map(Number);
    let currentTime = hours * 60 + minutes;
    
    const formatTime = (totalMinutes) => {
      const h = Math.floor(totalMinutes / 60);
      const m = totalMinutes % 60;
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    };
    
    let periodCount = 0;
    let slotNumber = 0;
    
    while (periodCount < periodsPerDay) {
      slotNumber++;
      periodCount++;
      
      // Add regular period
      slots.push({
        slot_number: slotNumber,
        type: 'period',
        name_ar: `الحصة ${periodCount}`,
        name_en: `Period ${periodCount}`,
        start_time: formatTime(currentTime),
        end_time: formatTime(currentTime + periodDuration),
        duration: periodDuration,
      });
      currentTime += periodDuration;
      
      // Add break after 3rd period
      if (periodCount === 3 && breakDuration > 0) {
        slotNumber++;
        slots.push({
          slot_number: slotNumber,
          type: 'break',
          name_ar: 'استراحة',
          name_en: 'Break',
          start_time: formatTime(currentTime),
          end_time: formatTime(currentTime + breakDuration),
          duration: breakDuration,
        });
        currentTime += breakDuration;
      }
      
      // Add prayer break after 5th or 6th period
      if ((periodCount === 5 || periodCount === 6) && prayerDuration > 0 && !slots.some(s => s.type === 'prayer')) {
        slotNumber++;
        slots.push({
          slot_number: slotNumber,
          type: 'prayer',
          name_ar: 'صلاة الظهر',
          name_en: 'Dhuhr Prayer',
          start_time: formatTime(currentTime),
          end_time: formatTime(currentTime + prayerDuration),
          duration: prayerDuration,
        });
        currentTime += prayerDuration;
      }
    }
    
    // Calculate end time
    const calculatedEnd = formatTime(currentTime);
    
    return { slots, endTime: calculatedEnd };
  };
  
  // Handler for auto-calculate button
  const handleAutoCalculate = () => {
    const { slots, endTime } = calculateTimeSlots(
      editedDayTimes.dayStart,
      editedDayTimes.periodsPerDay,
      editedDayTimes.periodDuration,
      editedDayTimes.breakDuration,
      editedDayTimes.prayerDuration
    );
    setCalculatedSlots(slots);
    setEditedDayTimes(prev => ({ ...prev, dayEnd: endTime }));
    setShowCalculatedPreview(true);
    toast.success('تم حساب التوزيع الزمني بنجاح');
  };
  
  // Data States
  const [schoolInfo, setSchoolInfo] = useState({});
  const [settings, setSettings] = useState({});
  const [teachers, setTeachers] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teacherRanks, setTeacherRanks] = useState([]);
  const [constraints, setConstraints] = useState([]);
  const [stages, setStages] = useState([]);
  const [grades, setGrades] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [defaultSettings, setDefaultSettings] = useState({});
  
  // Official Curriculum States - المنهج الرسمي
  const [officialCurriculumStats, setOfficialCurriculumStats] = useState(null);
  const [officialStages, setOfficialStages] = useState([]);
  const [officialTracks, setOfficialTracks] = useState([]);
  const [officialGrades, setOfficialGrades] = useState([]);
  const [officialSubjects, setOfficialSubjects] = useState([]);
  const [officialRankLoads, setOfficialRankLoads] = useState([]);
  const [selectedOfficialStage, setSelectedOfficialStage] = useState('');
  const [selectedOfficialTrack, setSelectedOfficialTrack] = useState('');
  const [selectedOfficialGrade, setSelectedOfficialGrade] = useState('');
  const [officialGradeCurriculum, setOfficialGradeCurriculum] = useState(null);
  
  // Fetch all data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [
        settingsRes,
        teachersRes,
        classesRes,
        ranksRes,
        constraintsRes,
        stagesRes,
        gradesRes,
        tracksRes,
        subjectsRes,
        defaultSettingsRes,
        assignmentsRes,
        refSubjectsRes,
        auditLogsRes
      ] = await Promise.all([
        api.get('/school/settings').catch(() => ({ data: {} })),
        api.get('/teachers').catch(() => ({ data: [] })),
        api.get('/classes').catch(() => ({ data: [] })),
        api.get('/reference/teacher-ranks').catch(() => ({ data: [] })),
        api.get('/school/constraints').catch(() => ({ data: [] })),
        api.get('/reference/stages').catch(() => ({ data: [] })),
        api.get('/reference/grades').catch(() => ({ data: [] })),
        api.get('/reference/tracks').catch(() => ({ data: [] })),
        api.get('/school/subjects').catch(() => ({ data: [] })), // Changed to school-specific subjects
        api.get('/reference/default-settings').catch(() => ({ data: {} })),
        api.get('/teacher-assignments').catch(() => ({ data: [] })),
        api.get('/reference/subjects').catch(() => ({ data: [] })), // Keep reference subjects for templates
        api.get('/school/settings/audit-logs?limit=10').catch(() => ({ data: { logs: [] } })),
      ]);
      
      const settingsData = settingsRes.data || {};
      
      setSchoolInfo(settingsData.school_info || {});
      setSettings({
        workingDays: settingsData.settings?.working_days_ar || ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس'],
        weekendDays: settingsData.settings?.weekend_days_ar || ['الجمعة', 'السبت'],
        periodsPerDay: settingsData.periods_per_day || settingsData.settings?.periods_per_day || 7,
        periodDuration: settingsData.settings?.period_duration_minutes || 45,
        breakDuration: settingsData.settings?.break_duration_minutes || 20,
        prayerDuration: settingsData.settings?.prayer_duration_minutes || 20,
        dayStart: settingsData.school_day_start || settingsData.settings?.school_day_start || '07:00',
        dayEnd: settingsData.school_day_end || settingsData.settings?.school_day_end || '13:15',
        timeSlots: settingsData.time_slots || settingsData.settings?.time_slots || [],
      });
      
      setTeachers(teachersRes.data || []);
      setClasses(classesRes.data || []);
      setTeacherRanks(ranksRes.data || []);
      setConstraints(constraintsRes.data || []);
      setStages(stagesRes.data || []);
      setGrades(gradesRes.data || []);
      setTracks(tracksRes.data || []);
      setDefaultSettings(defaultSettingsRes.data || {});
      setAssignments(assignmentsRes.data || []);
      setReferenceSubjects(refSubjectsRes.data || []);
      setAuditLogs(auditLogsRes.data?.logs || []);
      setLastSync(settingsData.last_sync || settingsData.settings?.updated_at || new Date().toISOString());
      
      // Get unique subjects for display
      const allSubjects = subjectsRes.data || [];
      const uniqueSubjects = allSubjects.reduce((acc, curr) => {
        if (!acc.find(s => s.name_ar === curr.name_ar)) {
          acc.push(curr);
        }
        return acc;
      }, []);
      setSubjects(uniqueSubjects.slice(0, 20)); // Show first 20 unique
      
      // Fetch Official Curriculum Data
      try {
        const [
          officialStatsRes,
          officialStagesRes,
          officialTracksRes,
          officialRankLoadsRes,
          officialSubjectsRes
        ] = await Promise.all([
          api.get('/official-curriculum/stats').catch(() => ({ data: null })),
          api.get('/official-curriculum/stages').catch(() => ({ data: [] })),
          api.get('/official-curriculum/tracks').catch(() => ({ data: [] })),
          api.get('/official-curriculum/teacher-rank-loads').catch(() => ({ data: [] })),
          api.get('/official-curriculum/subjects').catch(() => ({ data: [] })),
        ]);
        
        setOfficialCurriculumStats(officialStatsRes.data);
        setOfficialStages(officialStagesRes.data || []);
        setOfficialTracks(officialTracksRes.data || []);
        setOfficialRankLoads(officialRankLoadsRes.data || []);
        setOfficialSubjects(officialSubjectsRes.data || []);
      } catch (e) {
        console.error('Error fetching official curriculum:', e);
      }
      
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('خطأ في تحميل البيانات');
    } finally {
      setLoading(false);
    }
  }, [api]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // Fetch official curriculum for a specific grade
  const fetchOfficialGradeCurriculum = async (gradeId) => {
    if (!gradeId) {
      setOfficialGradeCurriculum(null);
      return;
    }
    try {
      const res = await api.get(`/official-curriculum/curriculum-for-grade/${gradeId}`);
      setOfficialGradeCurriculum(res.data);
    } catch (error) {
      console.error('Error fetching grade curriculum:', error);
      setOfficialGradeCurriculum(null);
    }
  };
  
  // Fetch official grades when stage/track changes
  const fetchOfficialGrades = async (stageId, trackId) => {
    try {
      let url = '/official-curriculum/grades';
      const params = [];
      if (stageId) params.push(`stage_id=${stageId}`);
      if (trackId) params.push(`track_id=${trackId}`);
      if (params.length > 0) url += '?' + params.join('&');
      
      const res = await api.get(url);
      setOfficialGrades(res.data || []);
    } catch (error) {
      console.error('Error fetching official grades:', error);
      setOfficialGrades([]);
    }
  };
  
  // Effect for official curriculum filters
  useEffect(() => {
    if ((selectedOfficialStage || selectedOfficialTrack) && api) {
      fetchOfficialGrades(selectedOfficialStage, selectedOfficialTrack);
    }
  }, [selectedOfficialStage, selectedOfficialTrack, api]);
  
  // Effect for grade curriculum
  useEffect(() => {
    if (selectedOfficialGrade && api) {
      fetchOfficialGradeCurriculum(selectedOfficialGrade);
    } else {
      setOfficialGradeCurriculum(null);
    }
  }, [selectedOfficialGrade, api]);
  
  // Fetch timetable readiness data
  const fetchReadinessData = async () => {
    setReadinessLoading(true);
    try {
      const res = await api.get('/timetable-readiness/check');
      setReadinessData(res.data);
    } catch (error) {
      console.error('Error fetching readiness data:', error);
    } finally {
      setReadinessLoading(false);
    }
  };
  
  // Fetch readiness on mount and after settings changes
  useEffect(() => {
    if (api) {
      fetchReadinessData();
    }
  }, [api, settings, teachers, classes, constraints]);
  
  // Save day times settings
  const saveDayTimes = async () => {
    setSaving(true);
    try {
      // Generate new time slots based on settings
      const newTimeSlots = [];
      let currentTime = editedDayTimes.dayStart;
      
      const addMinutes = (time, minutes) => {
        const [h, m] = time.split(':').map(Number);
        const totalMinutes = h * 60 + m + minutes;
        const newH = Math.floor(totalMinutes / 60);
        const newM = totalMinutes % 60;
        return `${String(newH).padStart(2, '0')}:${String(newM).padStart(2, '0')}`;
      };
      
      for (let i = 1; i <= editedDayTimes.periodsPerDay; i++) {
        const endTime = addMinutes(currentTime, editedDayTimes.periodDuration);
        newTimeSlots.push({
          slot_number: i,
          name_ar: `الحصة ${['الأولى', 'الثانية', 'الثالثة', 'الرابعة', 'الخامسة', 'السادسة', 'السابعة', 'الثامنة'][i-1] || i}`,
          name: `Period ${i}`,
          start_time: currentTime,
          end_time: endTime,
          duration_minutes: editedDayTimes.periodDuration,
          type: 'period',
          is_break: false,
        });
        currentTime = endTime;
        
        // Add break after 3rd period
        if (i === 3) {
          const breakEnd = addMinutes(currentTime, editedDayTimes.breakDuration);
          newTimeSlots.push({
            slot_number: null,
            name_ar: 'الاستراحة',
            name: 'Break',
            start_time: currentTime,
            end_time: breakEnd,
            duration_minutes: editedDayTimes.breakDuration,
            type: 'break',
            is_break: true,
          });
          currentTime = breakEnd;
        }
        
        // Add prayer after 5th period
        if (i === 5) {
          const prayerEnd = addMinutes(currentTime, editedDayTimes.prayerDuration);
          newTimeSlots.push({
            slot_number: null,
            name_ar: 'فترة الصلاة',
            name: 'Prayer',
            start_time: currentTime,
            end_time: prayerEnd,
            duration_minutes: editedDayTimes.prayerDuration,
            type: 'prayer',
            is_break: true,
          });
          currentTime = prayerEnd;
        }
      }
      
      await api.put('/school/settings', {
        settings: {
          school_day_start: editedDayTimes.dayStart,
          school_day_end: editedDayTimes.dayEnd,
          periods_per_day: editedDayTimes.periodsPerDay,
          period_duration_minutes: editedDayTimes.periodDuration,
          break_duration_minutes: editedDayTimes.breakDuration,
          prayer_duration_minutes: editedDayTimes.prayerDuration,
          time_slots: newTimeSlots,
        }
      });
      
      toast.success('تم حفظ مواعيد اليوم الدراسي بنجاح');
      setEditDayTimesOpen(false);
      fetchData();
    } catch (error) {
      console.error('Error saving:', error);
      toast.error(error.response?.data?.detail || 'فشل حفظ الإعدادات');
    } finally {
      setSaving(false);
    }
  };
  
  // State for inline time editing
  const [inlineTimeSlots, setInlineTimeSlots] = useState([]);
  const [savingInline, setSavingInline] = useState(false);
  
  // Initialize inline slots from settings
  useEffect(() => {
    if (settings.time_slots?.length > 0) {
      setInlineTimeSlots([...settings.time_slots]);
    }
  }, [settings.time_slots]);
  
  // Helper function to add minutes to time
  const addMinutesToTime = (time, minutes) => {
    const [h, m] = time.split(':').map(Number);
    const totalMinutes = h * 60 + m + minutes;
    const newH = Math.floor(totalMinutes / 60);
    const newM = totalMinutes % 60;
    return `${String(newH).padStart(2, '0')}:${String(newM).padStart(2, '0')}`;
  };
  
  // Handle inline time change with cascading recalculation
  const handleInlineTimeChange = async (slotIndex, newStartTime) => {
    // Clone slots for modification
    const updatedSlots = [...inlineTimeSlots];
    const currentSlot = updatedSlots[slotIndex];
    
    // Calculate duration of current slot
    const duration = currentSlot.duration_minutes || currentSlot.duration || 45;
    
    // Update current slot
    updatedSlots[slotIndex] = {
      ...currentSlot,
      start_time: newStartTime,
      end_time: addMinutesToTime(newStartTime, duration)
    };
    
    // Cascade update all following slots
    let currentEndTime = updatedSlots[slotIndex].end_time;
    
    for (let i = slotIndex + 1; i < updatedSlots.length; i++) {
      const slot = updatedSlots[i];
      const slotDuration = slot.duration_minutes || slot.duration || 45;
      
      updatedSlots[i] = {
        ...slot,
        start_time: currentEndTime,
        end_time: addMinutesToTime(currentEndTime, slotDuration)
      };
      
      currentEndTime = updatedSlots[i].end_time;
    }
    
    // Update state immediately for UI
    setInlineTimeSlots(updatedSlots);
    
    // Save to database
    setSavingInline(true);
    try {
      await api.put('/school/settings', {
        settings: {
          time_slots: updatedSlots,
          school_day_start: updatedSlots[0]?.start_time,
          school_day_end: updatedSlots[updatedSlots.length - 1]?.end_time
        }
      });
      
      toast.success('تم تحديث التوزيع الزمني بنجاح');
      
      // Update main settings state
      setSettings(prev => ({
        ...prev,
        time_slots: updatedSlots,
        school_day_start: updatedSlots[0]?.start_time,
        school_day_end: updatedSlots[updatedSlots.length - 1]?.end_time
      }));
    } catch (error) {
      console.error('Error saving inline time change:', error);
      toast.error('فشل حفظ التعديل، جاري استعادة القيم السابقة');
      // Revert to previous state
      setInlineTimeSlots([...settings.time_slots]);
    } finally {
      setSavingInline(false);
    }
  };
  
  // Reset time slots to default
  const handleResetTimeSlots = async () => {
    const defaultSlots = calculateTimeSlots('07:00', 7, 45, 20, 20).slots;
    setInlineTimeSlots(defaultSlots);
    
    setSavingInline(true);
    try {
      await api.put('/school/settings', {
        settings: {
          time_slots: defaultSlots,
          school_day_start: '07:00',
          school_day_end: defaultSlots[defaultSlots.length - 1]?.end_time
        }
      });
      toast.success('تم إعادة ضبط التوزيع الزمني للوضع الافتراضي');
      fetchData();
    } catch (error) {
      console.error('Error resetting:', error);
      toast.error('فشل إعادة الضبط');
    } finally {
      setSavingInline(false);
    }
  };
  
  // Toggle constraint active status
  const toggleConstraint = async (constraint) => {
    try {
      await api.put(`/school/constraints/${constraint.id}`, {
        is_active: !constraint.is_active
      });
      toast.success(`تم ${constraint.is_active ? 'تعطيل' : 'تفعيل'} القيد بنجاح`);
      fetchData();
    } catch (error) {
      console.error('Error toggling constraint:', error);
      toast.error('فشل تحديث القيد');
    }
  };
  
  // =============== SUBJECTS CRUD ===============
  // Add Subject
  const handleAddSubject = async () => {
    if (!newSubject.name_ar) {
      toast.error('يرجى إدخال اسم المادة');
      return;
    }
    
    setSaving(true);
    try {
      await api.post('/school/subjects', newSubject);
      toast.success('تم إضافة المادة بنجاح');
      setAddSubjectOpen(false);
      setNewSubject({ name_ar: '', name_en: '', weekly_periods: 4, category: 'general' });
      fetchData();
    } catch (error) {
      console.error('Error adding subject:', error);
      toast.error(error.response?.data?.detail || 'فشل إضافة المادة');
    } finally {
      setSaving(false);
    }
  };
  
  // Update Subject
  const handleUpdateSubject = async () => {
    if (!editSubject || !editSubject.name_ar) {
      toast.error('يرجى إدخال اسم المادة');
      return;
    }
    
    setSaving(true);
    try {
      await api.put(`/school/subjects/${editSubject.id}`, editSubject);
      toast.success('تم تحديث المادة بنجاح');
      setEditSubjectOpen(false);
      setEditSubject(null);
      fetchData();
    } catch (error) {
      console.error('Error updating subject:', error);
      toast.error(error.response?.data?.detail || 'فشل تحديث المادة');
    } finally {
      setSaving(false);
    }
  };
  
  // Delete Subject
  const handleDeleteSubject = async (subjectId) => {
    if (!window.confirm('هل أنت متأكد من حذف هذه المادة؟')) return;
    
    try {
      await api.delete(`/school/subjects/${subjectId}`);
      toast.success('تم حذف المادة بنجاح');
      fetchData();
    } catch (error) {
      console.error('Error deleting subject:', error);
      toast.error(error.response?.data?.detail || 'فشل حذف المادة');
    }
  };
  
  // =============== CONSTRAINTS CRUD ===============
  // Add Constraint
  const handleAddConstraint = async () => {
    if (!newConstraint.name_ar) {
      toast.error('يرجى إدخال اسم القيد');
      return;
    }
    
    setSaving(true);
    try {
      await api.post('/school/constraints', newConstraint);
      toast.success('تم إضافة القيد بنجاح');
      setAddConstraintOpen(false);
      setNewConstraint({ name_ar: '', description_ar: '', priority: 'medium', type: 'hard' });
      fetchData();
    } catch (error) {
      console.error('Error adding constraint:', error);
      toast.error(error.response?.data?.detail || 'فشل إضافة القيد');
    } finally {
      setSaving(false);
    }
  };
  
  // Update Constraint
  const handleUpdateConstraint = async () => {
    if (!editConstraint || !editConstraint.name_ar) {
      toast.error('يرجى إدخال اسم القيد');
      return;
    }
    
    setSaving(true);
    try {
      await api.put(`/school/constraints/${editConstraint.id}`, editConstraint);
      toast.success('تم تحديث القيد بنجاح');
      setEditConstraintOpen(false);
      setEditConstraint(null);
      fetchData();
    } catch (error) {
      console.error('Error updating constraint:', error);
      toast.error(error.response?.data?.detail || 'فشل تحديث القيد');
    } finally {
      setSaving(false);
    }
  };
  
  // Delete Constraint
  const handleDeleteConstraint = async (constraintId) => {
    if (!window.confirm('هل أنت متأكد من حذف هذا القيد؟')) return;
    
    try {
      await api.delete(`/school/constraints/${constraintId}`);
      toast.success('تم حذف القيد بنجاح');
      fetchData();
    } catch (error) {
      console.error('Error deleting constraint:', error);
      toast.error(error.response?.data?.detail || 'فشل حذف القيد');
    }
  };
  
  // =============== TEACHER ASSIGNMENTS CRUD ===============
  // Add Assignment
  const handleAddAssignment = async () => {
    if (!newAssignment.teacher_id || !newAssignment.class_id || !newAssignment.subject_id) {
      toast.error('يرجى تعبئة جميع الحقول المطلوبة');
      return;
    }
    
    setSaving(true);
    try {
      const schoolId = user?.tenant_id || schoolInfo?.id || 'SCH-001';
      await api.post('/teacher-assignments', {
        ...newAssignment,
        school_id: schoolId,
        academic_year: '2026-2027',
        semester: 1
      });
      toast.success('تم إضافة الإسناد بنجاح');
      setAddAssignmentOpen(false);
      setNewAssignment({ teacher_id: '', class_id: '', subject_id: '', weekly_sessions: 4 });
      fetchData();
    } catch (error) {
      console.error('Error adding assignment:', error);
      toast.error(error.response?.data?.detail || 'فشل إضافة الإسناد');
    } finally {
      setSaving(false);
    }
  };
  
  // Update Assignment
  const handleUpdateAssignment = async () => {
    if (!editAssignment) return;
    
    setSaving(true);
    try {
      await api.put(`/teacher-assignments/${editAssignment.id}`, {
        teacher_id: editAssignment.teacher_id,
        class_id: editAssignment.class_id,
        subject_id: editAssignment.subject_id,
        weekly_sessions: editAssignment.weekly_sessions
      });
      toast.success('تم تحديث الإسناد بنجاح');
      setEditAssignmentOpen(false);
      setEditAssignment(null);
      fetchData();
    } catch (error) {
      console.error('Error updating assignment:', error);
      toast.error(error.response?.data?.detail || 'فشل تحديث الإسناد');
    } finally {
      setSaving(false);
    }
  };
  
  // Delete Assignment
  const handleDeleteAssignment = async (assignmentId) => {
    if (!window.confirm('هل أنت متأكد من حذف هذا الإسناد؟')) return;
    
    try {
      await api.delete(`/teacher-assignments/${assignmentId}`);
      toast.success('تم حذف الإسناد بنجاح');
      fetchData();
    } catch (error) {
      console.error('Error deleting assignment:', error);
      toast.error(error.response?.data?.detail || 'فشل حذف الإسناد');
    }
  };
  
  // =============== SCHOOL INFO UPDATE ===============
  const handleUpdateSchoolInfo = async () => {
    setSaving(true);
    try {
      await api.put('/school/settings/info', editedSchoolInfo);
      toast.success('تم تحديث معلومات المدرسة بنجاح');
      setEditSchoolInfoOpen(false);
      fetchData();
    } catch (error) {
      console.error('Error updating school info:', error);
      toast.error(error.response?.data?.detail || 'فشل تحديث معلومات المدرسة');
    } finally {
      setSaving(false);
    }
  };
  
  // =============== WORK DAYS UPDATE ===============
  const handleSaveWorkDays = async () => {
    setSaving(true);
    try {
      await api.put('/school/settings/work-days', editedWorkDays);
      toast.success('تم تحديث أيام العمل بنجاح');
      setEditWorkDaysOpen(false);
      fetchData();
    } catch (error) {
      console.error('Error saving work days:', error);
      toast.error(error.response?.data?.detail || 'فشل حفظ أيام العمل');
    } finally {
      setSaving(false);
    }
  };
  
  const toggleWorkDay = (day) => {
    setEditedWorkDays(prev => ({ ...prev, [day]: !prev[day] }));
  };
  
  // =============== STAGES CRUD ===============
  const handleAddStage = async () => {
    if (!newStage.name) {
      toast.error('يرجى إدخال اسم المرحلة');
      return;
    }
    
    setSaving(true);
    try {
      await api.post('/school/settings/stages', newStage);
      toast.success('تم إضافة المرحلة التعليمية بنجاح');
      setAddStageOpen(false);
      setNewStage({ name: '', name_en: '', order: 1 });
      fetchData();
    } catch (error) {
      console.error('Error adding stage:', error);
      toast.error(error.response?.data?.detail || 'فشل إضافة المرحلة');
    } finally {
      setSaving(false);
    }
  };
  
  const handleUpdateStage = async () => {
    if (!editStage || !editStage.name) {
      toast.error('يرجى إدخال اسم المرحلة');
      return;
    }
    
    setSaving(true);
    try {
      await api.put(`/school/settings/stages/${editStage.id}`, editStage);
      toast.success('تم تحديث المرحلة التعليمية بنجاح');
      setEditStageOpen(false);
      setEditStage(null);
      fetchData();
    } catch (error) {
      console.error('Error updating stage:', error);
      toast.error(error.response?.data?.detail || 'فشل تحديث المرحلة');
    } finally {
      setSaving(false);
    }
  };
  
  const handleDeleteStage = async (stageId, stageName) => {
    try {
      const result = await api.delete(`/school/settings/stages/${stageId}`);
      if (result.data?.warning) {
        setDeleteTarget({ type: 'stage', id: stageId, name: stageName, dependencies: result.data.dependencies });
        setDeleteConfirmOpen(true);
      } else {
        toast.success('تم حذف المرحلة التعليمية بنجاح');
        fetchData();
      }
    } catch (error) {
      console.error('Error deleting stage:', error);
      toast.error(error.response?.data?.detail || 'فشل حذف المرحلة');
    }
  };
  
  // Toggle stage active status
  const handleToggleStage = async (stageId, isActive) => {
    try {
      await api.put(`/school/settings/stages/${stageId}`, { is_active: isActive });
      toast.success(`تم ${isActive ? 'تفعيل' : 'تعطيل'} المرحلة بنجاح`);
      // Update stages locally
      setStages(prev => prev.map(s => s.id === stageId ? { ...s, is_active: isActive } : s));
    } catch (error) {
      console.error('Error toggling stage:', error);
      toast.error('فشل تحديث حالة المرحلة');
    }
  };
  
  // =============== GRADES CRUD ===============
  const handleAddGrade = async () => {
    if (!newGrade.name || !newGrade.stage_id) {
      toast.error('يرجى إدخال اسم الصف واختيار المرحلة');
      return;
    }
    
    setSaving(true);
    try {
      await api.post('/school/settings/grades', newGrade);
      toast.success('تم إضافة الصف الدراسي بنجاح');
      setAddGradeOpen(false);
      setNewGrade({ name: '', name_en: '', stage_id: '' });
      fetchData();
    } catch (error) {
      console.error('Error adding grade:', error);
      toast.error(error.response?.data?.detail || 'فشل إضافة الصف');
    } finally {
      setSaving(false);
    }
  };
  
  const handleUpdateGrade = async () => {
    if (!editGrade || !editGrade.name) {
      toast.error('يرجى إدخال اسم الصف');
      return;
    }
    
    setSaving(true);
    try {
      await api.put(`/school/settings/grades/${editGrade.id}`, editGrade);
      toast.success('تم تحديث الصف الدراسي بنجاح');
      setEditGradeOpen(false);
      setEditGrade(null);
      fetchData();
    } catch (error) {
      console.error('Error updating grade:', error);
      toast.error(error.response?.data?.detail || 'فشل تحديث الصف');
    } finally {
      setSaving(false);
    }
  };
  
  const handleDeleteGrade = async (gradeId, gradeName) => {
    try {
      const result = await api.delete(`/school/settings/grades/${gradeId}`);
      if (result.data?.warning) {
        setDeleteTarget({ type: 'grade', id: gradeId, name: gradeName, dependencies: result.data.dependencies });
        setDeleteConfirmOpen(true);
      } else {
        toast.success('تم حذف الصف الدراسي بنجاح');
        fetchData();
      }
    } catch (error) {
      console.error('Error deleting grade:', error);
      toast.error(error.response?.data?.detail || 'فشل حذف الصف');
    }
  };
  
  // =============== DELETE WITH CONFIRMATION ===============
  const handleDeleteWithDependencies = async (subjectId) => {
    try {
      const result = await api.delete(`/school/subjects/${subjectId}`);
      if (result.data?.warning) {
        setDeleteTarget({ type: 'subject', id: subjectId, name: result.data.subject_name, dependencies: result.data.dependencies });
        setDeleteConfirmOpen(true);
      } else {
        toast.success('تم حذف المادة بنجاح');
        fetchData();
      }
    } catch (error) {
      console.error('Error deleting subject:', error);
      toast.error(error.response?.data?.detail || 'فشل حذف المادة');
    }
  };
  
  const confirmDelete = async () => {
    try {
      if (deleteTarget.type === 'subject') {
        await api.delete(`/school/subjects/${deleteTarget.id}?force=true`);
      } else if (deleteTarget.type === 'stage') {
        await api.delete(`/school/settings/stages/${deleteTarget.id}?force=true`);
      } else if (deleteTarget.type === 'grade') {
        await api.delete(`/school/settings/grades/${deleteTarget.id}?force=true`);
      }
      toast.success('تم الحذف بنجاح');
      setDeleteConfirmOpen(false);
      setDeleteTarget({ type: '', id: '', name: '', dependencies: null });
      fetchData();
    } catch (error) {
      console.error('Error force deleting:', error);
      toast.error(error.response?.data?.detail || 'فشل الحذف');
    }
  };
  
  // Loading state
  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-muted/20 to-background">
          <div className="text-center">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center mx-auto mb-6 animate-pulse">
              <Settings className="h-10 w-10 text-white" />
            </div>
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-brand-navy mb-4" />
            <p className="text-muted-foreground font-medium">جاري تحميل إعدادات المدرسة...</p>
          </div>
        </div>
      </Sidebar>
    );
  }
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-background via-muted/10 to-background" data-testid="school-settings-page-pro">
        
        {/* Header */}
        <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-lg border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center shadow-lg">
                <Settings className="h-7 w-7 text-white" />
              </div>
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground">
                  مرحباً، {user?.full_name || 'المستخدم'}
                </h1>
                <p className="text-base text-muted-foreground">إعدادات المدرسة</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" onClick={toggleTheme}>
                      {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {isDark ? 'الوضع النهاري' : 'الوضع الليلي'}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button variant="outline" onClick={fetchData} className="gap-2">
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                تحديث
              </Button>
              <NotificationBell />
            </div>
          </div>
        </header>
        
        {/* Main Content */}
        <main className="p-6 space-y-6 max-w-7xl mx-auto">
          
          {/* School Info Card */}
          <Card className="border-2 border-brand-navy/20 bg-gradient-to-r from-brand-navy/5 via-brand-turquoise/5 to-brand-navy/5 overflow-hidden">
            <CardContent className="p-6">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div className="flex items-center gap-5">
                  <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center shadow-xl">
                    <Building2 className="h-10 w-10 text-white" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-cairo text-2xl font-bold">{schoolInfo.name || 'اسم المدرسة'}</h2>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-8 w-8"
                        onClick={() => {
                          setEditedSchoolInfo({
                            name: schoolInfo.name || '',
                            name_en: schoolInfo.name_en || '',
                            city: schoolInfo.city || '',
                            address: schoolInfo.address || '',
                            phone: schoolInfo.phone || '',
                            email: schoolInfo.email || '',
                          });
                          setEditSchoolInfoOpen(true);
                        }}
                        data-testid="edit-school-info-btn"
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                    </div>
                    <p className="text-sm text-muted-foreground">{schoolInfo.name_en || 'School Name'}</p>
                    <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-4 w-4" /> {schoolInfo.city || 'المدينة'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Phone className="h-4 w-4" /> {schoolInfo.phone || '---'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Mail className="h-4 w-4" /> {schoolInfo.email || '---'}
                      </span>
                    </div>
                    {/* Last Sync Indicator */}
                    <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                      <CheckCircle2 className="h-3 w-3 text-green-500" />
                      <span>آخر مزامنة: {lastSync ? new Date(lastSync).toLocaleString('ar-SA') : 'غير متاح'}</span>
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-4">
                  <div className="text-center px-4 py-3 bg-gradient-to-br from-violet-100 to-violet-50 rounded-xl border border-violet-200 shadow-sm">
                    <p className="text-3xl font-bold text-violet-700">{teachers.length}</p>
                    <p className="text-xs text-violet-600 font-medium">معلم</p>
                  </div>
                  <div className="text-center px-4 py-3 bg-gradient-to-br from-cyan-100 to-cyan-50 rounded-xl border border-cyan-200 shadow-sm">
                    <p className="text-3xl font-bold text-cyan-700">{classes.length}</p>
                    <p className="text-xs text-cyan-600 font-medium">فصل</p>
                  </div>
                  <div className="text-center px-4 py-3 bg-gradient-to-br from-emerald-100 to-emerald-50 rounded-xl border border-emerald-200 shadow-sm">
                    <p className="text-3xl font-bold text-emerald-700">{subjects.length}</p>
                    <p className="text-xs text-emerald-600 font-medium">مادة</p>
                  </div>
                  <div className="text-center px-4 py-3 bg-gradient-to-br from-blue-100 to-blue-50 rounded-xl border border-blue-200 shadow-sm">
                    <p className="text-3xl font-bold text-blue-700">{settings.periodsPerDay}</p>
                    <p className="text-xs text-blue-600 font-medium">حصة/يوم</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Tabs Navigation - Reorganized into Two Sections */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full" dir="rtl">
            {/* Section Headers */}
            <div className="mb-4 space-y-4">
              {/* القسم الأول: البيانات المتغيرة */}
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                    <Settings className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-bold text-blue-800">البيانات المتغيرة لبناء الجدول</h3>
                    <p className="text-xs text-blue-600">Dynamic Timetable Inputs - المدخلات التشغيلية لمحرك الجدول</p>
                  </div>
                </div>
                <TabsList className="grid w-full grid-cols-4 lg:grid-cols-7 h-auto p-1 bg-white/50">
                  <TabsTrigger value="overview" className="text-xs py-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white" data-testid="tab-overview">
                    <Calendar className="h-4 w-4 ml-1 hidden sm:inline" />
                    نظرة عامة
                  </TabsTrigger>
                  <TabsTrigger value="work-days" className="text-xs py-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white" data-testid="tab-work-days">
                    <CalendarDays className="h-4 w-4 ml-1 hidden sm:inline" />
                    أيام العمل
                  </TabsTrigger>
                  <TabsTrigger value="time" className="text-xs py-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white" data-testid="tab-time">
                    <Timer className="h-4 w-4 ml-1 hidden sm:inline" />
                    التوقيت
                  </TabsTrigger>
                  <TabsTrigger value="classes" className="text-xs py-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white" data-testid="tab-classes">
                    <GraduationCap className="h-4 w-4 ml-1 hidden sm:inline" />
                    الفصول
                  </TabsTrigger>
                  <TabsTrigger value="teachers" className="text-xs py-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white" data-testid="tab-teachers">
                    <Users className="h-4 w-4 ml-1 hidden sm:inline" />
                    المعلمون
                  </TabsTrigger>
                  <TabsTrigger value="assignments" className="text-xs py-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white" data-testid="tab-assignments">
                    <Target className="h-4 w-4 ml-1 hidden sm:inline" />
                    الإسنادات
                  </TabsTrigger>
                  <TabsTrigger value="constraints" className="text-xs py-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white" data-testid="tab-constraints">
                    <Shield className="h-4 w-4 ml-1 hidden sm:inline" />
                    القيود
                  </TabsTrigger>
                </TabsList>
              </div>
              
              {/* القسم الثاني: البيانات الرسمية الثابتة */}
              <div className="bg-gradient-to-r from-emerald-50 to-green-50 border-2 border-emerald-200 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center">
                    <School className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-bold text-emerald-800">البيانات الأساسية الثابتة</h3>
                    <p className="text-xs text-emerald-600">Official Static Reference Data - بيانات وزارة التعليم الرسمية</p>
                  </div>
                  <Badge className="mr-auto bg-emerald-100 text-emerald-700 border-emerald-300">
                    <Shield className="h-3 w-3 ml-1" />
                    للقراءة فقط
                  </Badge>
                </div>
                <TabsList className="grid w-full grid-cols-2 lg:grid-cols-2 h-auto p-1 bg-white/50 max-w-md">
                  <TabsTrigger value="official-curriculum" className="text-xs py-2 data-[state=active]:bg-emerald-600 data-[state=active]:text-white" data-testid="tab-official-curriculum">
                    <BookOpen className="h-4 w-4 ml-1 hidden sm:inline" />
                    المنهج الرسمي
                  </TabsTrigger>
                  <TabsTrigger value="structure" className="text-xs py-2 data-[state=active]:bg-emerald-600 data-[state=active]:text-white" data-testid="tab-structure">
                    <Layers className="h-4 w-4 ml-1 hidden sm:inline" />
                    الهيكل الأكاديمي
                  </TabsTrigger>
                </TabsList>
              </div>
            </div>
            
            {/* ================= Timetable Readiness Card ================= */}
            {readinessData && (
              <Card className={`border-2 mb-4 ${
                readinessData.status === 'FULLY_READY' ? 'border-green-300 bg-green-50' :
                readinessData.status === 'PARTIALLY_READY' ? 'border-amber-300 bg-amber-50' :
                'border-red-300 bg-red-50'
              }`} data-testid="readiness-card">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {/* Status Icon */}
                      <div className={`w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg ${
                        readinessData.status === 'FULLY_READY' ? 'bg-gradient-to-br from-green-500 to-emerald-600' :
                        readinessData.status === 'PARTIALLY_READY' ? 'bg-gradient-to-br from-amber-500 to-yellow-600' :
                        'bg-gradient-to-br from-red-500 to-rose-600'
                      }`}>
                        {readinessData.status === 'FULLY_READY' ? (
                          <CheckCircle2 className="h-7 w-7 text-white" />
                        ) : readinessData.status === 'PARTIALLY_READY' ? (
                          <AlertTriangle className="h-7 w-7 text-white" />
                        ) : (
                          <AlertCircle className="h-7 w-7 text-white" />
                        )}
                      </div>
                      
                      {/* Status Text */}
                      <div>
                        <h3 className={`text-lg font-bold ${
                          readinessData.status === 'FULLY_READY' ? 'text-green-800' :
                          readinessData.status === 'PARTIALLY_READY' ? 'text-amber-800' :
                          'text-red-800'
                        }`}>
                          {readinessData.status === 'FULLY_READY' ? 'النظام جاهز بالكامل لإنشاء الجدول' :
                           readinessData.status === 'PARTIALLY_READY' ? 'النظام جاهز جزئياً - يمكن المتابعة مع تحذيرات' :
                           'البيانات غير مكتملة - لا يمكن إنشاء الجدول'}
                        </h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          نسبة الجاهزية: {readinessData.percentage}% • 
                          {readinessData.summary?.critical_count > 0 && (
                            <span className="text-red-600 mr-2">{readinessData.summary.critical_count} مشكلة حرجة</span>
                          )}
                          {readinessData.summary?.warning_count > 0 && (
                            <span className="text-amber-600 mr-2">{readinessData.summary.warning_count} تحذير</span>
                          )}
                        </p>
                      </div>
                    </div>
                    
                    {/* Progress Circle */}
                    <div className="hidden md:flex flex-col items-center gap-2">
                      <div className={`relative w-16 h-16 rounded-full flex items-center justify-center border-4 ${
                        readinessData.status === 'FULLY_READY' ? 'border-green-400' :
                        readinessData.status === 'PARTIALLY_READY' ? 'border-amber-400' :
                        'border-red-400'
                      }`}>
                        <span className={`text-xl font-bold ${
                          readinessData.status === 'FULLY_READY' ? 'text-green-700' :
                          readinessData.status === 'PARTIALLY_READY' ? 'text-amber-700' :
                          'text-red-700'
                        }`}>{Math.round(readinessData.percentage)}%</span>
                      </div>
                      <span className="text-xs text-muted-foreground">جاهزية النظام</span>
                    </div>
                    
                    {/* Action Button */}
                    <Button 
                      className={`${
                        readinessData.can_generate 
                          ? 'bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700' 
                          : 'bg-gray-400 cursor-not-allowed'
                      }`}
                      disabled={!readinessData.can_generate}
                      onClick={() => window.location.href = '/principal/timetable'}
                      data-testid="generate-timetable-btn"
                    >
                      <Play className="h-4 w-4 ml-2" />
                      {readinessData.can_generate ? 'معالجة الجدول بالذكاء الاصطناعي' : 'أكمل البيانات أولاً'}
                    </Button>
                  </div>
                  
                  {/* Issues Summary */}
                  {(readinessData.critical_issues?.length > 0 || readinessData.warnings?.length > 0) && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <p className="text-sm font-medium text-muted-foreground mb-2">المشاكل المكتشفة:</p>
                      <div className="grid md:grid-cols-2 gap-2 max-h-32 overflow-y-auto">
                        {readinessData.critical_issues?.slice(0, 4).map((issue, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-sm p-2 bg-red-100 rounded-lg">
                            <Ban className="h-4 w-4 text-red-600 flex-shrink-0" />
                            <span className="text-red-700 truncate">{issue.message_ar}</span>
                            {issue.fix_link && (
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className="h-6 px-2 text-xs text-red-600 hover:bg-red-200 mr-auto"
                                onClick={() => setActiveTab(issue.fix_link?.split('tab=')[1] || 'overview')}
                              >
                                إصلاح
                              </Button>
                            )}
                          </div>
                        ))}
                        {readinessData.warnings?.slice(0, 2).map((issue, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-sm p-2 bg-amber-100 rounded-lg">
                            <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0" />
                            <span className="text-amber-700 truncate">{issue.message_ar}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Categories Progress - Collapsed View */}
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(readinessData.categories || {}).map(([key, cat]) => (
                        <Badge 
                          key={key}
                          className={`${
                            cat.status === 'ready' ? 'bg-green-100 text-green-700 border-green-300' :
                            cat.status === 'warning' ? 'bg-amber-100 text-amber-700 border-amber-300' :
                            'bg-red-100 text-red-700 border-red-300'
                          }`}
                        >
                          {cat.status === 'ready' ? '✓' : cat.status === 'warning' ? '!' : '✗'} {cat.name_ar} ({cat.score}/{cat.max_score})
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
            
            {/* ================= TAB: نظرة عامة ================= */}
            <TabsContent value="overview" className="space-y-6">
              {/* أيام العمل والعطلة - التصميم الجديد */}
              <div className="grid lg:grid-cols-2 gap-6">
                <Card className="border-2 border-green-200 overflow-hidden">
                  <CardHeader className="pb-4 bg-gradient-to-r from-green-50 to-emerald-50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-md">
                          <Calendar className="h-6 w-6 text-white" />
                        </div>
                        <div>
                          <CardTitle className="text-lg">أيام العمل والعطلة</CardTitle>
                          <CardDescription className="text-sm">
                            الجدول الأسبوعي للمدرسة
                          </CardDescription>
                        </div>
                      </div>
                      <Button 
                        variant="outline" 
                        size="sm"
                        className="border-green-500 text-green-700 hover:bg-green-100"
                        onClick={() => {
                          setEditedWorkDays({
                            sunday: settings.workingDays?.includes('الأحد') ?? true,
                            monday: settings.workingDays?.includes('الإثنين') ?? true,
                            tuesday: settings.workingDays?.includes('الثلاثاء') ?? true,
                            wednesday: settings.workingDays?.includes('الأربعاء') ?? true,
                            thursday: settings.workingDays?.includes('الخميس') ?? true,
                            friday: settings.weekendDays?.includes('الجمعة') ?? false,
                            saturday: settings.weekendDays?.includes('السبت') ?? false,
                          });
                          setEditWorkDaysOpen(true);
                        }}
                        data-testid="edit-work-days-btn"
                      >
                        <Edit2 className="h-4 w-4 ml-1" />
                        تعديل
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="p-6">
                    {/* كروت الأيام - تصميم بسيط وأنيق */}
                    <div className="flex flex-wrap justify-center gap-2 mb-5">
                      {[
                        { key: 'sunday', name: 'الأحد' },
                        { key: 'monday', name: 'الإثنين' },
                        { key: 'tuesday', name: 'الثلاثاء' },
                        { key: 'wednesday', name: 'الأربعاء' },
                        { key: 'thursday', name: 'الخميس' },
                        { key: 'friday', name: 'الجمعة' },
                        { key: 'saturday', name: 'السبت' },
                      ].map((day) => {
                        const isWorkDay = settings.workingDays?.includes(day.name);
                        
                        return (
                          <div
                            key={day.key}
                            className={`
                              px-4 py-2 rounded-full text-sm font-medium transition-all duration-200
                              ${isWorkDay 
                                ? 'bg-gradient-to-r from-emerald-500 to-green-500 text-white shadow-md shadow-green-200/50' 
                                : 'bg-gray-100 text-gray-500 border border-gray-200'
                              }
                            `}
                          >
                            {day.name}
                          </div>
                        );
                      })}
                    </div>
                    
                    {/* ملخص */}
                    <div className="flex items-center justify-center gap-6 pt-4 border-t">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-gradient-to-r from-emerald-500 to-green-500"></div>
                        <span className="text-sm text-muted-foreground">{settings.workingDays?.length || 5} أيام دراسة</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-gray-300"></div>
                        <span className="text-sm text-muted-foreground">{settings.weekendDays?.length || 2} أيام عطلة</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* اليوم الدراسي */}
                <Card className="border-2 border-blue-200">
                  <CardHeader className="pb-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                          <Clock className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <CardTitle className="text-base">اليوم الدراسي</CardTitle>
                          <CardDescription className="text-xs">
                            {settings.periodsPerDay} حصص • {settings.periodDuration} دقيقة للحصة
                          </CardDescription>
                        </div>
                      </div>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => {
                          setEditedDayTimes({
                            dayStart: settings.dayStart || '07:00',
                            dayEnd: settings.dayEnd || '13:15',
                            periodsPerDay: settings.periodsPerDay || 7,
                            periodDuration: settings.periodDuration || 45,
                            breakDuration: settings.breakDuration || 20,
                            prayerDuration: settings.prayerDuration || 20,
                          });
                          setEditDayTimesOpen(true);
                        }}
                        data-testid="edit-day-times-btn"
                      >
                        <Edit2 className="h-4 w-4 ml-1" />
                        تعديل
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-4 bg-gradient-to-br from-green-100 to-green-50 rounded-xl border border-green-200">
                        <Sun className="h-6 w-6 mx-auto mb-2 text-green-600" />
                        <p className="text-2xl font-bold text-green-700">{settings.dayStart}</p>
                        <p className="text-xs text-green-600">بداية الدوام</p>
                      </div>
                      <div className="text-center p-4 bg-gradient-to-br from-orange-100 to-orange-50 rounded-xl border border-orange-200">
                        <Moon className="h-6 w-6 mx-auto mb-2 text-orange-600" />
                        <p className="text-2xl font-bold text-orange-700">{settings.dayEnd}</p>
                        <p className="text-xs text-orange-600">نهاية الدوام</p>
                      </div>
                    </div>
                    <Separator className="my-4" />
                    <div className="grid grid-cols-3 gap-3">
                      <div className="text-center p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <p className="text-xl font-bold text-blue-700">{settings.periodsPerDay}</p>
                        <p className="text-xs text-blue-600">حصة</p>
                      </div>
                      <div className="text-center p-3 bg-amber-50 rounded-lg border border-amber-200">
                        <p className="text-xl font-bold text-amber-700">{settings.breakDuration}</p>
                        <p className="text-xs text-amber-600">د. استراحة</p>
                      </div>
                      <div className="text-center p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                        <p className="text-xl font-bold text-emerald-700">{settings.prayerDuration}</p>
                        <p className="text-xs text-emerald-600">د. صلاة</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
              
              {/* ملخص سريع */}
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard 
                  title="المعلمون" 
                  value={teachers.length} 
                  icon={Users} 
                  color="border-violet-200"
                  onClick={() => setActiveTab('teachers')}
                />
                <StatCard 
                  title="الفصول" 
                  value={classes.length} 
                  icon={GraduationCap} 
                  color="border-cyan-200"
                  onClick={() => setActiveTab('classes')}
                />
                <StatCard 
                  title="رتب المعلمين" 
                  value={teacherRanks.length} 
                  icon={Award} 
                  color="border-teal-200"
                  onClick={() => setActiveTab('ranks')}
                />
                <StatCard 
                  title="القيود الإدارية" 
                  value={constraints.length} 
                  icon={Shield} 
                  color="border-rose-200"
                  onClick={() => setActiveTab('constraints')}
                />
              </div>
            </TabsContent>
            
            {/* ================= TAB: أيام العمل والعطلة - التصميم الجديد ================= */}
            <TabsContent value="work-days" className="space-y-6" data-testid="work-days-tab-content">
              <Card className="border-2 border-blue-200">
                <CardHeader className="bg-gradient-to-r from-blue-50 to-indigo-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-md">
                        <CalendarDays className="h-6 w-6 text-white" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">أيام العمل والعطلة</CardTitle>
                        <CardDescription>تحديد أيام الدراسة والعطلة الأسبوعية</CardDescription>
                      </div>
                    </div>
                    <Button 
                      variant="outline" 
                      size="sm"
                      className="border-blue-500 text-blue-700 hover:bg-blue-100"
                      onClick={() => {
                        setEditedWorkDays({
                          sunday: settings.workingDays?.includes('الأحد') ?? true,
                          monday: settings.workingDays?.includes('الإثنين') ?? true,
                          tuesday: settings.workingDays?.includes('الثلاثاء') ?? true,
                          wednesday: settings.workingDays?.includes('الأربعاء') ?? true,
                          thursday: settings.workingDays?.includes('الخميس') ?? true,
                          friday: settings.weekendDays?.includes('الجمعة') ?? false,
                          saturday: settings.weekendDays?.includes('السبت') ?? false,
                        });
                        setEditWorkDaysOpen(true);
                      }}
                      data-testid="edit-work-days-btn-new"
                    >
                      <Edit2 className="h-4 w-4 ml-1" />
                      تعديل
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-6">
                  {/* أيام الأسبوع - Grid واضح مع Toggle */}
                  <div className="grid grid-cols-7 gap-3 mb-6">
                    {[
                      { key: 'sunday', name: 'الأحد', nameEn: 'Sunday' },
                      { key: 'monday', name: 'الإثنين', nameEn: 'Monday' },
                      { key: 'tuesday', name: 'الثلاثاء', nameEn: 'Tuesday' },
                      { key: 'wednesday', name: 'الأربعاء', nameEn: 'Wednesday' },
                      { key: 'thursday', name: 'الخميس', nameEn: 'Thursday' },
                      { key: 'friday', name: 'الجمعة', nameEn: 'Friday' },
                      { key: 'saturday', name: 'السبت', nameEn: 'Saturday' },
                    ].map((day) => {
                      const isWorkDay = settings.workingDays?.includes(day.name);
                      
                      return (
                        <Card
                          key={day.key}
                          className={`transition-all duration-300 cursor-pointer hover:scale-105 ${
                            isWorkDay 
                              ? 'bg-gradient-to-br from-green-100 to-emerald-50 border-2 border-green-400 shadow-lg shadow-green-200/50' 
                              : 'bg-gradient-to-br from-red-50 to-rose-50 border-2 border-red-200'
                          }`}
                          data-testid={`day-card-${day.key}`}
                        >
                          <CardContent className="p-4 text-center">
                            <p className="text-xs text-muted-foreground mb-1">{day.nameEn}</p>
                            <p className={`text-lg font-bold mb-2 ${isWorkDay ? 'text-green-700' : 'text-red-600'}`}>
                              {day.name}
                            </p>
                            <div className={`
                              inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium
                              ${isWorkDay 
                                ? 'bg-green-500 text-white' 
                                : 'bg-red-400 text-white'
                              }
                            `}>
                              {isWorkDay ? (
                                <>
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                  يوم دراسة
                                </>
                              ) : (
                                <>
                                  <Ban className="h-3.5 w-3.5" />
                                  عطلة
                                </>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                  
                  {/* ملخص أيام العمل */}
                  <div className="grid md:grid-cols-2 gap-4 p-4 bg-gray-50 rounded-xl border">
                    <div className="flex items-center gap-4 p-4 bg-white rounded-lg border border-green-200">
                      <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                        <CheckCircle2 className="h-6 w-6 text-green-600" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-green-700">{settings.workingDays?.length || 5}</p>
                        <p className="text-sm text-green-600">أيام دراسة أسبوعياً</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 p-4 bg-white rounded-lg border border-red-200">
                      <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                        <Ban className="h-6 w-6 text-red-600" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-red-600">{settings.weekendDays?.length || 2}</p>
                        <p className="text-sm text-red-500">أيام عطلة أسبوعياً</p>
                      </div>
                    </div>
                  </div>
                  
                  {/* ملاحظة توضيحية */}
                  <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200 flex items-start gap-2">
                    <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-blue-700">
                      تحديد أيام العمل يؤثر مباشرة على محرك الجدول الذكي. 
                      عند تغيير أيام العمل، قد تحتاج إلى إعادة توليد الجدول المدرسي.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* ================= TAB: المنهج الرسمي ================= */}
            <TabsContent value="official-curriculum" className="space-y-6" data-testid="official-curriculum-tab-content">
              {/* Header Card */}
              <Card className="border-2 border-emerald-300 bg-gradient-to-r from-emerald-50 to-green-50">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center shadow-lg">
                        <School className="h-7 w-7 text-white" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-emerald-800">المنهج الرسمي - وزارة التعليم</h2>
                        <p className="text-sm text-emerald-600">
                          بيانات رسمية مغلقة • للقراءة فقط • مصدر الحقيقة للجدولة الذكية
                        </p>
                      </div>
                    </div>
                    <Badge className="bg-emerald-100 text-emerald-800 border-2 border-emerald-300 px-4 py-2 text-sm font-bold">
                      <Shield className="h-4 w-4 ml-2" />
                      بيانات مقفلة
                    </Badge>
                  </div>
                  
                  {/* Stats Grid */}
                  {officialCurriculumStats && (
                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mt-6">
                      <div className="text-center p-3 bg-white rounded-xl border border-emerald-200 shadow-sm">
                        <p className="text-2xl font-bold text-emerald-700">{officialCurriculumStats.stages}</p>
                        <p className="text-xs text-emerald-600">مرحلة تعليمية</p>
                      </div>
                      <div className="text-center p-3 bg-white rounded-xl border border-emerald-200 shadow-sm">
                        <p className="text-2xl font-bold text-emerald-700">{officialCurriculumStats.tracks}</p>
                        <p className="text-xs text-emerald-600">مسار تعليمي</p>
                      </div>
                      <div className="text-center p-3 bg-white rounded-xl border border-emerald-200 shadow-sm">
                        <p className="text-2xl font-bold text-emerald-700">{officialCurriculumStats.grades}</p>
                        <p className="text-xs text-emerald-600">صف دراسي</p>
                      </div>
                      <div className="text-center p-3 bg-white rounded-xl border border-emerald-200 shadow-sm">
                        <p className="text-2xl font-bold text-emerald-700">{officialCurriculumStats.subjects}</p>
                        <p className="text-xs text-emerald-600">مادة دراسية</p>
                      </div>
                      <div className="text-center p-3 bg-white rounded-xl border border-emerald-200 shadow-sm">
                        <p className="text-2xl font-bold text-emerald-700">{officialCurriculumStats.grade_subject_mappings}</p>
                        <p className="text-xs text-emerald-600">توزيع مادة/صف</p>
                      </div>
                      <div className="text-center p-3 bg-white rounded-xl border border-emerald-200 shadow-sm">
                        <p className="text-2xl font-bold text-emerald-700">{officialCurriculumStats.teacher_rank_loads}</p>
                        <p className="text-xs text-emerald-600">رتبة معلم</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
              
              <div className="grid lg:grid-cols-2 gap-6">
                {/* المراحل الدراسية */}
                <Card className="border-2 border-emerald-200">
                  <CardHeader className="bg-gradient-to-r from-emerald-50 to-green-50">
                    <CardTitle className="flex items-center gap-2 text-emerald-800">
                      <Layers className="h-5 w-5" />
                      المراحل الدراسية الرسمية
                      <Badge variant="outline" className="mr-auto text-emerald-600 border-emerald-300">
                        {officialStages.length} مرحلة
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4">
                    <div className="space-y-3">
                      {officialStages.map((stage) => (
                        <div 
                          key={stage.id} 
                          className={`flex items-center justify-between p-4 rounded-xl border-2 transition-all cursor-pointer ${
                            selectedOfficialStage === stage.id 
                              ? 'bg-emerald-100 border-emerald-400' 
                              : 'bg-white border-gray-200 hover:border-emerald-300'
                          }`}
                          onClick={() => {
                            setSelectedOfficialStage(selectedOfficialStage === stage.id ? '' : stage.id);
                            setSelectedOfficialGrade('');
                          }}
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-400 to-green-500 flex items-center justify-center">
                              <span className="text-white font-bold">{stage.order}</span>
                            </div>
                            <div>
                              <p className="font-bold text-emerald-900">{stage.name_ar}</p>
                              <p className="text-xs text-emerald-600">{stage.name_en} • {stage.grades_count} صفوف</p>
                            </div>
                          </div>
                          <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">
                            <Shield className="h-3 w-3 ml-1" />
                            رسمي
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
                
                {/* المسارات التعليمية */}
                <Card className="border-2 border-blue-200">
                  <CardHeader className="bg-gradient-to-r from-blue-50 to-indigo-50">
                    <CardTitle className="flex items-center gap-2 text-blue-800">
                      <ArrowRight className="h-5 w-5" />
                      المسارات التعليمية الرسمية
                      <Badge variant="outline" className="mr-auto text-blue-600 border-blue-300">
                        {officialTracks.length} مسار
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4">
                    <div className="space-y-3">
                      {officialTracks.map((track) => (
                        <div 
                          key={track.id} 
                          className={`flex items-center justify-between p-4 rounded-xl border-2 transition-all cursor-pointer ${
                            selectedOfficialTrack === track.id 
                              ? 'bg-blue-100 border-blue-400' 
                              : 'bg-white border-gray-200 hover:border-blue-300'
                          }`}
                          onClick={() => {
                            setSelectedOfficialTrack(selectedOfficialTrack === track.id ? '' : track.id);
                            setSelectedOfficialGrade('');
                          }}
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center">
                              <span className="text-white font-bold">{track.order}</span>
                            </div>
                            <div>
                              <p className="font-bold text-blue-900">{track.name_ar}</p>
                              <p className="text-xs text-blue-600">{track.name_en}</p>
                            </div>
                          </div>
                          <Badge className="bg-blue-50 text-blue-700 border-blue-200">
                            <Shield className="h-3 w-3 ml-1" />
                            رسمي
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
              
              {/* الصفوف الدراسية - يظهر بعد اختيار المرحلة أو المسار */}
              {(selectedOfficialStage || selectedOfficialTrack) && (
                <Card className="border-2 border-purple-200">
                  <CardHeader className="bg-gradient-to-r from-purple-50 to-violet-50">
                    <CardTitle className="flex items-center gap-2 text-purple-800">
                      <GraduationCap className="h-5 w-5" />
                      الصفوف الدراسية
                      <Badge variant="outline" className="mr-auto text-purple-600 border-purple-300">
                        {officialGrades.length} صف
                      </Badge>
                    </CardTitle>
                    <CardDescription>
                      اختر صفاً لعرض المنهج الدراسي الكامل
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4">
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {officialGrades.map((grade) => (
                        <div 
                          key={grade.id} 
                          className={`p-4 rounded-xl border-2 transition-all cursor-pointer ${
                            selectedOfficialGrade === grade.id 
                              ? 'bg-purple-100 border-purple-400 shadow-md' 
                              : 'bg-white border-gray-200 hover:border-purple-300 hover:shadow-sm'
                          }`}
                          onClick={() => setSelectedOfficialGrade(selectedOfficialGrade === grade.id ? '' : grade.id)}
                        >
                          <p className="font-bold text-purple-900">{grade.name_ar}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <Badge variant="outline" className="text-xs">{grade.stage_name_ar}</Badge>
                            <Badge variant="outline" className="text-xs">{grade.track_name_ar}</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* المنهج الكامل للصف المختار */}
              {officialGradeCurriculum && (
                <Card className="border-2 border-amber-200">
                  <CardHeader className="bg-gradient-to-r from-amber-50 to-orange-50">
                    <CardTitle className="flex items-center gap-2 text-amber-800">
                      <BookOpen className="h-5 w-5" />
                      المنهج الدراسي: {officialGradeCurriculum.grade?.name_ar}
                    </CardTitle>
                    <CardDescription className="flex items-center gap-4 mt-2">
                      <span>{officialGradeCurriculum.stage?.name_ar}</span>
                      <span>•</span>
                      <span>{officialGradeCurriculum.track?.name_ar}</span>
                      <span>•</span>
                      <Badge className="bg-amber-100 text-amber-800">
                        {officialGradeCurriculum.summary?.subjects_count} مادة
                      </Badge>
                      <Badge className="bg-amber-100 text-amber-800">
                        {officialGradeCurriculum.summary?.total_weekly_periods} حصة/أسبوع
                      </Badge>
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b-2 border-amber-200">
                            <th className="text-right py-3 px-4 font-bold text-amber-800">المادة</th>
                            <th className="text-center py-3 px-4 font-bold text-amber-800">التصنيف</th>
                            <th className="text-center py-3 px-4 font-bold text-amber-800">أساسية</th>
                            <th className="text-center py-3 px-4 font-bold text-amber-800">حصص/سنة</th>
                            <th className="text-center py-3 px-4 font-bold text-amber-800">حصص/أسبوع</th>
                          </tr>
                        </thead>
                        <tbody>
                          {officialGradeCurriculum.subjects?.map((subject, idx) => (
                            <tr key={idx} className="border-b border-amber-100 hover:bg-amber-50 transition-colors">
                              <td className="py-3 px-4">
                                <div>
                                  <p className="font-medium">{subject.subject_name_ar}</p>
                                  <p className="text-xs text-muted-foreground">{subject.subject_name_en}</p>
                                </div>
                              </td>
                              <td className="text-center py-3 px-4">
                                <Badge className={`text-xs ${
                                  CATEGORY_COLORS[subject.category]?.bg || 'bg-gray-100'
                                } ${CATEGORY_COLORS[subject.category]?.text || 'text-gray-700'}`}>
                                  {subject.category === 'islamic' ? 'إسلامية' :
                                   subject.category === 'language' ? 'لغات' :
                                   subject.category === 'science' ? 'علوم' :
                                   subject.category === 'social' ? 'اجتماعية' :
                                   subject.category === 'technology' ? 'تقنية' :
                                   subject.category === 'activity' ? 'أنشطة' :
                                   subject.category === 'skills' ? 'مهارات' :
                                   subject.category === 'business' ? 'أعمال' : subject.category}
                                </Badge>
                              </td>
                              <td className="text-center py-3 px-4">
                                {subject.is_core ? (
                                  <Badge className="bg-green-100 text-green-700">أساسية</Badge>
                                ) : (
                                  <Badge variant="outline">اختيارية</Badge>
                                )}
                              </td>
                              <td className="text-center py-3 px-4 font-bold text-amber-700">
                                {subject.annual_periods}
                              </td>
                              <td className="text-center py-3 px-4 font-bold text-amber-800 text-lg">
                                {subject.weekly_periods}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="bg-amber-100 font-bold">
                            <td colSpan={3} className="py-3 px-4 text-amber-800">الإجمالي</td>
                            <td className="text-center py-3 px-4 text-amber-800">
                              {officialGradeCurriculum.summary?.total_annual_periods}
                            </td>
                            <td className="text-center py-3 px-4 text-amber-800 text-lg">
                              {officialGradeCurriculum.summary?.total_weekly_periods}
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* النصاب الرسمي للمعلمين */}
              <Card className="border-2 border-violet-200">
                <CardHeader className="bg-gradient-to-r from-violet-50 to-purple-50">
                  <CardTitle className="flex items-center gap-2 text-violet-800">
                    <Award className="h-5 w-5" />
                    النصاب الرسمي للمعلمين حسب الرتبة
                    <Badge variant="outline" className="mr-auto text-violet-600 border-violet-300">
                      {officialRankLoads.length} رتبة
                    </Badge>
                  </CardTitle>
                  <CardDescription>
                    وفقاً لنظام وزارة التعليم السعودية
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-4">
                  <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {officialRankLoads.map((rank) => (
                      <div 
                        key={rank.id} 
                        className={`p-4 rounded-xl border-2 ${
                          rank.is_special_education 
                            ? 'bg-gradient-to-br from-teal-50 to-cyan-50 border-teal-200' 
                            : 'bg-gradient-to-br from-violet-50 to-purple-50 border-violet-200'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <Badge className={rank.is_special_education ? 'bg-teal-100 text-teal-700' : 'bg-violet-100 text-violet-700'}>
                            {rank.is_special_education ? 'تربية خاصة' : 'تعليم عام'}
                          </Badge>
                          <Badge variant="outline" className="text-emerald-600 border-emerald-300">
                            <Shield className="h-3 w-3 ml-1" />
                            رسمي
                          </Badge>
                        </div>
                        <p className="font-bold text-lg">{rank.rank_name_ar}</p>
                        <p className="text-xs text-muted-foreground mb-3">{rank.rank_name_en}</p>
                        <div className="flex items-center justify-center p-3 bg-white rounded-lg border">
                          <span className="text-3xl font-bold text-violet-700">{rank.weekly_periods}</span>
                          <span className="text-sm text-violet-600 mr-2">حصة/أسبوع</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
              
              {/* ملاحظة توضيحية */}
              <Card className="border-2 border-gray-200 bg-gray-50">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-gray-500 mt-0.5" />
                    <div>
                      <p className="font-medium text-gray-700">ملاحظة مهمة</p>
                      <p className="text-sm text-gray-600 mt-1">
                        هذه البيانات رسمية من وزارة التعليم السعودية ولا يمكن تعديلها. 
                        تُستخدم كمصدر الحقيقة الأساسي لمحرك الجدولة الذكي لضمان توافق الجداول مع المتطلبات الرسمية.
                        لتخصيص إعدادات مدرستك، استخدم التبويبات الأخرى (المواد، الرتب، الهيكل).
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* ================= TAB: التوزيع الزمني ================= */}
            <TabsContent value="time" className="space-y-4">
              <Card className="border-2 border-purple-200">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-md">
                        <Timer className="h-6 w-6 text-white" />
                      </div>
                      <div>
                        <CardTitle>التوزيع الزمني الكامل لليوم الدراسي</CardTitle>
                        <CardDescription>
                          {inlineTimeSlots?.length || settings.time_slots?.length || 0} فترة زمنية • انقر على الوقت للتعديل المباشر
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {savingInline && (
                        <Badge className="bg-blue-100 text-blue-700 animate-pulse">
                          <Loader2 className="h-3 w-3 animate-spin ml-1" />
                          جاري الحفظ...
                        </Badge>
                      )}
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={handleResetTimeSlots}
                        className="border-amber-500 text-amber-700 hover:bg-amber-50"
                        data-testid="reset-time-slots-btn"
                      >
                        <RefreshCw className="h-4 w-4 ml-1" />
                        إعادة الضبط
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* ملاحظة توضيحية */}
                  <div className="p-3 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200 mb-4">
                    <p className="text-sm text-purple-700 flex items-center gap-2">
                      <Info className="h-4 w-4" />
                      <span>
                        <strong>التعديل المباشر:</strong> انقر على أي وقت لتعديله مباشرة. سيتم إعادة حساب جميع الفترات التالية تلقائياً والحفظ فوراً.
                      </span>
                    </p>
                  </div>
                  
                  {(inlineTimeSlots?.length > 0 || settings.time_slots?.length > 0) ? (
                    <div className="space-y-3">
                      {(inlineTimeSlots?.length > 0 ? inlineTimeSlots : settings.time_slots || []).map((slot, index) => (
                        <TimeSlotInlineEdit 
                          key={slot.id || index} 
                          slot={slot} 
                          index={index}
                          allSlots={inlineTimeSlots?.length > 0 ? inlineTimeSlots : settings.time_slots || []}
                          onTimeChange={handleInlineTimeChange}
                          isSaving={savingInline}
                        />
                      ))}
                      
                      {/* ملخص اليوم الدراسي */}
                      <div className="mt-6 p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border-2 border-green-200">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <CheckCircle2 className="h-6 w-6 text-green-600" />
                            <div>
                              <p className="font-bold text-green-800">ملخص اليوم الدراسي</p>
                              <p className="text-sm text-green-600">
                                من {(inlineTimeSlots?.length > 0 ? inlineTimeSlots : settings.time_slots)?.[0]?.start_time || '07:00'} 
                                {' إلى '}
                                {(inlineTimeSlots?.length > 0 ? inlineTimeSlots : settings.time_slots)?.[(inlineTimeSlots?.length > 0 ? inlineTimeSlots : settings.time_slots || []).length - 1]?.end_time || '13:00'}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="text-center">
                              <p className="text-2xl font-bold text-blue-600">
                                {(inlineTimeSlots?.length > 0 ? inlineTimeSlots : settings.time_slots || []).filter(s => s.type === 'period' || !s.type).length}
                              </p>
                              <p className="text-xs text-muted-foreground">حصة</p>
                            </div>
                            <div className="text-center">
                              <p className="text-2xl font-bold text-amber-600">
                                {(inlineTimeSlots?.length > 0 ? inlineTimeSlots : settings.time_slots || []).filter(s => s.type === 'break').length}
                              </p>
                              <p className="text-xs text-muted-foreground">استراحة</p>
                            </div>
                            <div className="text-center">
                              <p className="text-2xl font-bold text-green-600">
                                {(inlineTimeSlots?.length > 0 ? inlineTimeSlots : settings.time_slots || []).filter(s => s.type === 'prayer').length}
                              </p>
                              <p className="text-xs text-muted-foreground">صلاة</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-12 text-muted-foreground">
                      <Timer className="h-16 w-16 mx-auto mb-4 opacity-30" />
                      <p className="text-lg font-medium">لا يوجد توزيع زمني محدد</p>
                      <p className="text-sm">انقر على الزر أدناه لإنشاء التوزيع الزمني الافتراضي</p>
                      <Button 
                        className="mt-4" 
                        onClick={handleResetTimeSlots}
                      >
                        <Plus className="h-4 w-4 ml-2" />
                        إنشاء التوزيع الزمني الافتراضي
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* ================= TAB: المعلمون ================= */}
            <TabsContent value="teachers" className="space-y-4">
              <Card className="border-2 border-violet-200">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-md">
                        <Users className="h-6 w-6 text-white" />
                      </div>
                      <div>
                        <CardTitle>بيانات المعلمين</CardTitle>
                        <CardDescription>{teachers.length} معلم في المدرسة</CardDescription>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-xs text-muted-foreground">
                      لإضافة معلم، انتقل إلى "إدارة المستخدمين والفصول"
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  {teachers.length > 0 ? (
                    <div className="space-y-3">
                      {teachers.map((teacher) => (
                        <TeacherItem key={teacher.id} teacher={teacher} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 text-muted-foreground">
                      <Users className="h-16 w-16 mx-auto mb-4 opacity-30" />
                      <p className="text-lg font-medium">لا يوجد معلمون مسجلون</p>
                      <p className="text-sm mt-2">انتقل إلى صفحة "إدارة المستخدمين والفصول" لإضافة معلمين</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* ================= TAB: الفصول ================= */}
            <TabsContent value="classes" className="space-y-4">
              <Card className="border-2 border-cyan-200">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center shadow-md">
                        <GraduationCap className="h-6 w-6 text-white" />
                      </div>
                      <div>
                        <CardTitle>بيانات الفصول</CardTitle>
                        <CardDescription>{classes.length} فصل في المدرسة</CardDescription>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-xs text-muted-foreground">
                      لإضافة فصل، انتقل إلى "إدارة المستخدمين والفصول"
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  {classes.length > 0 ? (
                    <div className="space-y-3">
                      {classes.map((classItem) => (
                        <ClassItem key={classItem.id} classItem={classItem} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 text-muted-foreground">
                      <GraduationCap className="h-16 w-16 mx-auto mb-4 opacity-30" />
                      <p className="text-lg font-medium">لا يوجد فصول مسجلة</p>
                      <p className="text-sm mt-2">انتقل إلى صفحة "إدارة المستخدمين والفصول" لإضافة فصول</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* ================= TAB: إسنادات المعلمين ================= */}
            <TabsContent value="assignments" className="space-y-4">
              <Card className="border-2 border-indigo-200">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-md">
                        <Target className="h-6 w-6 text-white" />
                      </div>
                      <div>
                        <CardTitle>إسنادات المعلمين والفصول</CardTitle>
                        <CardDescription>{assignments.length} إسناد - ربط المعلمين بالفصول والمواد</CardDescription>
                      </div>
                    </div>
                    <Button 
                      onClick={() => setAddAssignmentOpen(true)}
                      className="bg-indigo-600 hover:bg-indigo-700"
                      data-testid="add-assignment-btn"
                    >
                      <Plus className="h-4 w-4 ml-2" />
                      إضافة إسناد
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {assignments.length > 0 ? (
                    <div className="space-y-3">
                      {/* Group by teacher */}
                      {Object.entries(
                        assignments.reduce((acc, curr) => {
                          const key = curr.teacher_name || curr.teacher_id || 'غير محدد';
                          if (!acc[key]) acc[key] = [];
                          acc[key].push(curr);
                          return acc;
                        }, {})
                      ).map(([teacherName, teacherAssignments]) => (
                        <div key={teacherName} className="p-4 rounded-xl bg-gradient-to-r from-indigo-50 to-purple-50 border-2 border-indigo-200">
                          <div className="flex items-center gap-3 mb-3">
                            <div className="w-10 h-10 rounded-full bg-indigo-200 flex items-center justify-center">
                              <Users className="h-5 w-5 text-indigo-700" />
                            </div>
                            <div>
                              <p className="font-bold text-indigo-800">{teacherName}</p>
                              <p className="text-xs text-muted-foreground">{teacherAssignments.length} فصول/مواد</p>
                            </div>
                          </div>
                          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-2 mr-12">
                            {teacherAssignments.map((assignment) => (
                              <div 
                                key={assignment.id}
                                className="flex items-center justify-between p-3 rounded-lg bg-white border border-indigo-100 group hover:shadow-md transition-all"
                              >
                                <div className="flex items-center gap-2">
                                  <GraduationCap className="h-4 w-4 text-indigo-600" />
                                  <div>
                                    <p className="text-sm font-medium">{assignment.class_name || assignment.class_id}</p>
                                    <p className="text-xs text-muted-foreground">{assignment.subject_name || assignment.subject_id}</p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Badge variant="secondary" className="text-xs">{assignment.weekly_sessions} ح/أسبوع</Badge>
                                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-6 w-6 text-blue-500"
                                      onClick={() => {
                                        setEditAssignment(assignment);
                                        setEditAssignmentOpen(true);
                                      }}
                                    >
                                      <Edit2 className="h-3 w-3" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-6 w-6 text-red-500"
                                      onClick={() => handleDeleteAssignment(assignment.id)}
                                    >
                                      <Trash2 className="h-3 w-3" />
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 text-muted-foreground">
                      <Target className="h-16 w-16 mx-auto mb-4 opacity-30" />
                      <p className="text-lg font-medium">لا يوجد إسنادات مسجلة</p>
                      <p className="text-sm mb-4">قم بإضافة إسنادات لربط المعلمين بالفصول والمواد</p>
                      <Button 
                        className="bg-indigo-600 hover:bg-indigo-700"
                        onClick={() => setAddAssignmentOpen(true)}
                      >
                        <Plus className="h-4 w-4 ml-2" />
                        إضافة أول إسناد
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* ================= TAB: المواد الدراسية ================= */}
            {/* تم نقل المواد والرتب إلى تبويب المنهج الرسمي - لتجنب التكرار */}
            
            {/* ================= TAB: القيود الإدارية ================= */}
            <TabsContent value="constraints" className="space-y-6" data-testid="constraints-tab-content">
              {/* Header */}
              <Card className="border-2 border-rose-200 bg-gradient-to-r from-rose-50 to-pink-50">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-rose-500 to-pink-600 flex items-center justify-center shadow-lg">
                        <Shield className="h-7 w-7 text-white" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-rose-800">نظام قيود الجدول المدرسي</h2>
                        <p className="text-sm text-rose-600">
                          Timetable Constraints System - القيود الإلزامية والتفضيلية لمحرك الجدولة
                        </p>
                      </div>
                    </div>
                    <Button 
                      onClick={() => setAddConstraintOpen(true)}
                      className="bg-rose-600 hover:bg-rose-700"
                      data-testid="add-constraint-btn"
                    >
                      <Plus className="h-4 w-4 ml-2" />
                      إضافة قيد جديد
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Hard Constraints - القيود الإلزامية */}
              <Card className="border-2 border-red-300">
                <CardHeader className="bg-gradient-to-r from-red-50 to-rose-50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center">
                      <Ban className="h-5 w-5 text-white" />
                    </div>
                    <div className="flex-1">
                      <CardTitle className="text-red-800 flex items-center gap-2">
                        القيود الإلزامية
                        <Badge className="bg-red-100 text-red-700 border-red-300">Hard Constraints</Badge>
                      </CardTitle>
                      <CardDescription className="text-red-600">
                        لا يمكن خرقها إطلاقاً - أي انتهاك يمنع تعيين الحصة
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-4">
                  <div className="space-y-3">
                    {/* قائمة القيود الإلزامية الثابتة */}
                    {[
                      { id: 'no-teacher-conflict', name: 'لا يمكن تعيين معلم لحصتين في نفس الوقت', icon: Users, locked: true },
                      { id: 'no-class-conflict', name: 'لا يمكن تعيين فصل لحصتين في نفس الوقت', icon: GraduationCap, locked: true },
                      { id: 'no-subject-overlap', name: 'لا يمكن تعيين أكثر من مادة لنفس الفصل في نفس الحصة', icon: BookOpen, locked: true },
                      { id: 'within-school-day', name: 'لا يمكن وضع حصة خارج أوقات اليوم الدراسي', icon: Clock, locked: true },
                      { id: 'respect-breaks', name: 'لا يمكن وضع حصة داخل فترات الاستراحة أو الصلاة', icon: Coffee, locked: true },
                      { id: 'max-daily-periods', name: 'لا يمكن تجاوز الحد الأقصى للحصص اليومية للمعلم', icon: Calendar, locked: true },
                      { id: 'max-weekly-periods', name: 'لا يمكن تجاوز النصاب الأسبوعي للمعلم', icon: CalendarDays, locked: true },
                      { id: 'teacher-subject-match', name: 'لا يمكن إسناد مادة إلى معلم غير مؤهل لها', icon: Target, locked: true },
                      { id: 'weekly-periods-match', name: 'يجب احترام عدد الحصص الأسبوعية المطلوبة لكل مادة', icon: Grid3X3, locked: true },
                      { id: 'respect-unavailability', name: 'لا يمكن وضع حصة في فترة غير متاحة للمعلم أو الفصل', icon: Ban, locked: true },
                      { id: 'no-disabled-slots', name: 'لا يمكن استخدام فترات زمنية معطلة أو مغلقة', icon: AlertCircle, locked: true },
                      { id: 'room-requirements', name: 'يجب احترام متطلبات نوع الغرفة (مختبر، حاسب...)', icon: Building2, locked: true },
                    ].map((constraint) => (
                      <div 
                        key={constraint.id}
                        className="flex items-center justify-between p-4 bg-white rounded-xl border-2 border-red-100 hover:border-red-200 transition-all"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
                            <constraint.icon className="h-5 w-5 text-red-600" />
                          </div>
                          <div>
                            <p className="font-medium text-gray-800">{constraint.name}</p>
                            <p className="text-xs text-red-500">Hard Constraint - لا يمكن تعطيله</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className="bg-red-100 text-red-700">
                            <Shield className="h-3 w-3 ml-1" />
                            مقفل
                          </Badge>
                          <Switch checked={true} disabled className="data-[state=checked]:bg-red-500" />
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Soft Constraints - القيود التفضيلية */}
              <Card className="border-2 border-amber-300">
                <CardHeader className="bg-gradient-to-r from-amber-50 to-yellow-50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500 to-yellow-600 flex items-center justify-center">
                      <Star className="h-5 w-5 text-white" />
                    </div>
                    <div className="flex-1">
                      <CardTitle className="text-amber-800 flex items-center gap-2">
                        القيود التفضيلية
                        <Badge className="bg-amber-100 text-amber-700 border-amber-300">Soft Constraints</Badge>
                      </CardTitle>
                      <CardDescription className="text-amber-600">
                        يُفضل احترامها قدر الإمكان - تؤثر على جودة الجدول (Score)
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-4">
                  <div className="space-y-3">
                    {/* القيود التفضيلية من قاعدة البيانات + الثابتة */}
                    {[
                      { id: 'distribute-subjects', name: 'توزيع حصص المادة على أكثر من يوم', description: 'تجنب تكديس حصص نفس المادة في يوم واحد', weight: 8, editable: true },
                      { id: 'minimize-teacher-gaps', name: 'تقليل الفجوات في جدول المعلم', description: 'تقليل الحصص الفارغة بين حصص المعلم', weight: 7, editable: true },
                      { id: 'minimize-class-gaps', name: 'تقليل الفجوات في جدول الفصل', description: 'تقليل الحصص الفارغة للطلاب', weight: 7, editable: true },
                      { id: 'heavy-subjects-morning', name: 'المواد الثقيلة في أول اليوم', description: 'تجنب وضع الرياضيات والعلوم في آخر اليوم', weight: 6, editable: true },
                      { id: 'core-subjects-first', name: 'المواد الأساسية في أول الفترات', description: 'تفضيل الفترات الأولى للمواد الأساسية', weight: 5, editable: true },
                      { id: 'no-consecutive-same', name: 'عدم تكرار نفس المادة متتالياً', description: 'إلا عند الحاجة (حصص مدمجة)', weight: 4, editable: true },
                      { id: 'balance-weekly-load', name: 'موازنة الحمل التدريسي', description: 'توزيع متوازن بين أيام الأسبوع', weight: 5, editable: true },
                      { id: 'teacher-preferences', name: 'تفضيلات المعلم الزمنية', description: 'احترام الأوقات المفضلة للمعلم', weight: 3, editable: true },
                      { id: 'reserve-slots', name: 'إبقاء فترات احتياطية', description: 'للبدائل والطوارئ', weight: 2, editable: true },
                    ].map((constraint) => (
                      <div 
                        key={constraint.id}
                        className="flex items-center justify-between p-4 bg-white rounded-xl border-2 border-amber-100 hover:border-amber-200 transition-all"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
                            <Star className="h-5 w-5 text-amber-600" />
                          </div>
                          <div>
                            <p className="font-medium text-gray-800">{constraint.name}</p>
                            <p className="text-xs text-amber-600">{constraint.description}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-center">
                            <p className="text-xs text-muted-foreground">الوزن</p>
                            <Badge className="bg-amber-100 text-amber-800">{constraint.weight}/10</Badge>
                          </div>
                          <Switch 
                            checked={true} 
                            className="data-[state=checked]:bg-amber-500"
                          />
                          {constraint.editable && (
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                              <Edit2 className="h-4 w-4 text-amber-600" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Custom Constraints - القيود المخصصة من المدير */}
              <Card className="border-2 border-purple-200">
                <CardHeader className="bg-gradient-to-r from-purple-50 to-violet-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center">
                        <Settings className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <CardTitle className="text-purple-800">قيود مخصصة للمدرسة</CardTitle>
                        <CardDescription className="text-purple-600">
                          قيود إضافية أضافها مدير المدرسة - {constraints.length} قيد
                        </CardDescription>
                      </div>
                    </div>
                    <Button 
                      onClick={() => setAddConstraintOpen(true)}
                      variant="outline"
                      className="border-purple-400 text-purple-700 hover:bg-purple-100"
                    >
                      <Plus className="h-4 w-4 ml-2" />
                      إضافة قيد مخصص
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-4">
                  {constraints.length > 0 ? (
                    <div className="space-y-3">
                      {constraints.map((constraint, index) => (
                        <ConstraintItem 
                          key={constraint.id} 
                          constraint={constraint} 
                          index={index}
                          onToggle={toggleConstraint}
                          onEdit={() => {
                            setEditConstraint(constraint);
                            setEditConstraintOpen(true);
                          }}
                          onDelete={() => handleDeleteConstraint(constraint.id)}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Settings className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p className="font-medium">لا يوجد قيود مخصصة</p>
                      <p className="text-sm mt-1">يمكنك إضافة قيود خاصة بمدرستك</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* ملاحظة توضيحية */}
              <Card className="border-2 border-gray-200 bg-gray-50">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-gray-500 mt-0.5" />
                    <div>
                      <p className="font-medium text-gray-700">كيف يستخدم محرك الجدول هذه القيود؟</p>
                      <ul className="text-sm text-gray-600 mt-2 space-y-1 list-disc list-inside">
                        <li><span className="text-red-600 font-medium">القيود الإلزامية:</span> يتم التحقق منها أولاً - أي انتهاك يرفض التعيين فوراً</li>
                        <li><span className="text-amber-600 font-medium">القيود التفضيلية:</span> تُستخدم لحساب جودة الحل (Score) - الوزن الأعلى = أهمية أكبر</li>
                        <li><span className="text-purple-600 font-medium">القيود المخصصة:</span> قيود إضافية حسب احتياجات مدرستك</li>
                      </ul>
                      <p className="text-sm text-gray-500 mt-3">
                        يختار النظام الجدول صاحب أعلى Score مع احترام جميع القيود الإلزامية.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* ================= TAB: الهيكل الأكاديمي ================= */}
            <TabsContent value="structure" className="space-y-4">
              <AcademicStructureView 
                stages={stages} 
                grades={grades} 
                tracks={tracks}
                onAddStage={() => setAddStageOpen(true)}
                onEditStage={(stage) => {
                  setEditStage(stage);
                  setEditStageOpen(true);
                }}
                onDeleteStage={handleDeleteStage}
                onToggleStage={handleToggleStage}
                onAddGrade={(stageId) => {
                  setNewGrade({ name: '', name_en: '', stage_id: stageId });
                  setAddGradeOpen(true);
                }}
                onEditGrade={(grade) => {
                  setEditGrade(grade);
                  setEditGradeOpen(true);
                }}
                onDeleteGrade={handleDeleteGrade}
              />
            </TabsContent>
            
          </Tabs>
        </main>
        
        {/* ============================================ */}
        {/* Dialog تعديل مواعيد اليوم الدراسي - المحسّن */}
        {/* ============================================ */}
        <Dialog open={editDayTimesOpen} onOpenChange={(open) => {
          setEditDayTimesOpen(open);
          if (!open) {
            setShowCalculatedPreview(false);
            setCalculatedSlots([]);
          }
        }}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Clock className="h-5 w-5 text-blue-600" />
                تعديل مواعيد اليوم الدراسي
              </DialogTitle>
              <DialogDescription>
                أدخل وقت بداية الحصة الأولى فقط وسيتم حساب باقي الأوقات تلقائياً
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-6 py-4">
              {/* القسم الأول: الإدخال الأساسي */}
              <div className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200">
                <h4 className="font-bold text-blue-800 mb-4 flex items-center gap-2">
                  <Sun className="h-5 w-5" />
                  وقت بداية الحصة الأولى
                </h4>
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <Label htmlFor="dayStart" className="text-sm text-blue-700 mb-2 block">
                      حدد وقت بداية الدوام
                    </Label>
                    <Input
                      id="dayStart"
                      type="time"
                      value={editedDayTimes.dayStart}
                      onChange={(e) => {
                        setEditedDayTimes({...editedDayTimes, dayStart: e.target.value});
                        setShowCalculatedPreview(false);
                      }}
                      className="text-center text-2xl font-bold h-14 border-2 border-blue-300 focus:border-blue-500"
                      data-testid="first-period-start-time"
                    />
                  </div>
                  <div className="flex-1 p-4 bg-white rounded-xl text-center border border-blue-200">
                    <p className="text-xs text-muted-foreground mb-1">نهاية الدوام (محسوبة)</p>
                    <p className="text-2xl font-bold text-blue-700">{editedDayTimes.dayEnd}</p>
                  </div>
                </div>
              </div>
              
              <Separator />
              
              {/* إعدادات الحصص */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="periodsPerDay">عدد الحصص اليومية</Label>
                  <Select 
                    value={String(editedDayTimes.periodsPerDay)} 
                    onValueChange={(v) => {
                      setEditedDayTimes({...editedDayTimes, periodsPerDay: parseInt(v)});
                      setShowCalculatedPreview(false);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[5, 6, 7, 8].map(n => (
                        <SelectItem key={n} value={String(n)}>{n} حصص</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="periodDuration">مدة الحصة (دقيقة)</Label>
                  <Select 
                    value={String(editedDayTimes.periodDuration)} 
                    onValueChange={(v) => {
                      setEditedDayTimes({...editedDayTimes, periodDuration: parseInt(v)});
                      setShowCalculatedPreview(false);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[35, 40, 45, 50, 55].map(n => (
                        <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              {/* الاستراحة والصلاة */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="breakDuration" className="flex items-center gap-2">
                    <Coffee className="h-4 w-4 text-amber-600" />
                    مدة الاستراحة (دقيقة)
                  </Label>
                  <Select 
                    value={String(editedDayTimes.breakDuration)} 
                    onValueChange={(v) => {
                      setEditedDayTimes({...editedDayTimes, breakDuration: parseInt(v)});
                      setShowCalculatedPreview(false);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[10, 15, 20, 25, 30].map(n => (
                        <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="prayerDuration" className="flex items-center gap-2">
                    <Moon className="h-4 w-4 text-emerald-600" />
                    مدة الصلاة (دقيقة)
                  </Label>
                  <Select 
                    value={String(editedDayTimes.prayerDuration)} 
                    onValueChange={(v) => {
                      setEditedDayTimes({...editedDayTimes, prayerDuration: parseInt(v)});
                      setShowCalculatedPreview(false);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[10, 15, 20, 25, 30].map(n => (
                        <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              {/* زر حساب تلقائي */}
              <Button 
                onClick={handleAutoCalculate}
                className="w-full h-12 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700"
                data-testid="auto-calculate-btn"
              >
                <RefreshCw className="h-5 w-5 ml-2" />
                احسب التوزيع الزمني تلقائياً
              </Button>
              
              {/* معاينة النتيجة */}
              {showCalculatedPreview && calculatedSlots.length > 0 && (
                <div className="p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-300">
                  <h4 className="font-bold text-green-800 mb-3 flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5" />
                    معاينة التوزيع الزمني المحسوب
                  </h4>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {calculatedSlots.map((slot, idx) => (
                      <div 
                        key={idx} 
                        className={`flex items-center justify-between p-2 rounded-lg ${
                          slot.type === 'period' ? 'bg-blue-100' :
                          slot.type === 'break' ? 'bg-amber-100' : 'bg-emerald-100'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {slot.type === 'period' && <BookOpen className="h-4 w-4 text-blue-600" />}
                          {slot.type === 'break' && <Coffee className="h-4 w-4 text-amber-600" />}
                          {slot.type === 'prayer' && <Moon className="h-4 w-4 text-emerald-600" />}
                          <span className="font-medium text-sm">{slot.name_ar}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {slot.duration} دقيقة
                          </Badge>
                          <span className="font-mono text-sm font-bold">
                            {slot.start_time} - {slot.end_time}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 p-2 bg-green-200 rounded-lg text-center">
                    <p className="text-sm font-bold text-green-800">
                      إجمالي الوقت: من {editedDayTimes.dayStart} إلى {editedDayTimes.dayEnd}
                    </p>
                  </div>
                </div>
              )}
              
              {/* ملاحظة */}
              <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-xs text-blue-700 flex items-center gap-2">
                  <Info className="h-4 w-4" />
                  اضغط على "احسب التوزيع" لمعاينة الجدول، ثم "حفظ" لتطبيق التغييرات
                </p>
              </div>
            </div>
            
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setEditDayTimesOpen(false)}>
                إلغاء
              </Button>
              <Button 
                onClick={saveDayTimes} 
                disabled={saving || !showCalculatedPreview} 
                className="bg-green-600 hover:bg-green-700"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                حفظ التغييرات
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ============================================ */}
        {/* Dialog إضافة مادة جديدة */}
        {/* ============================================ */}
        <Dialog open={addSubjectOpen} onOpenChange={setAddSubjectOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-emerald-600" />
                إضافة مادة جديدة
              </DialogTitle>
              <DialogDescription>
                أدخل بيانات المادة الدراسية الجديدة
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="subject-name-ar">اسم المادة (عربي) *</Label>
                <Input
                  id="subject-name-ar"
                  value={newSubject.name_ar}
                  onChange={(e) => setNewSubject({...newSubject, name_ar: e.target.value})}
                  placeholder="مثال: الحاسب الآلي"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="subject-name-en">اسم المادة (إنجليزي)</Label>
                <Input
                  id="subject-name-en"
                  value={newSubject.name_en}
                  onChange={(e) => setNewSubject({...newSubject, name_en: e.target.value})}
                  placeholder="مثال: Computer Science"
                  dir="ltr"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="subject-periods">النصاب الأسبوعي</Label>
                  <Select 
                    value={String(newSubject.weekly_periods)} 
                    onValueChange={(v) => setNewSubject({...newSubject, weekly_periods: parseInt(v)})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 4, 5, 6, 7, 8].map(n => (
                        <SelectItem key={n} value={String(n)}>{n} حصص</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="subject-category">التصنيف</Label>
                  <Select 
                    value={newSubject.category} 
                    onValueChange={(v) => setNewSubject({...newSubject, category: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="language">لغات</SelectItem>
                      <SelectItem value="science">علوم</SelectItem>
                      <SelectItem value="islamic">إسلامية</SelectItem>
                      <SelectItem value="technology">تقنية</SelectItem>
                      <SelectItem value="activity">أنشطة</SelectItem>
                      <SelectItem value="social">اجتماعية</SelectItem>
                      <SelectItem value="skills">مهارات</SelectItem>
                      <SelectItem value="general">عام</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddSubjectOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleAddSubject} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Plus className="h-4 w-4 ml-2" />}
                إضافة
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ============================================ */}
        {/* Dialog تعديل مادة */}
        {/* ============================================ */}
        <Dialog open={editSubjectOpen} onOpenChange={setEditSubjectOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Edit2 className="h-5 w-5 text-blue-600" />
                تعديل المادة
              </DialogTitle>
            </DialogHeader>
            
            {editSubject && (
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="edit-subject-name-ar">اسم المادة (عربي) *</Label>
                  <Input
                    id="edit-subject-name-ar"
                    value={editSubject.name_ar}
                    onChange={(e) => setEditSubject({...editSubject, name_ar: e.target.value})}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="edit-subject-name-en">اسم المادة (إنجليزي)</Label>
                  <Input
                    id="edit-subject-name-en"
                    value={editSubject.name_en || ''}
                    onChange={(e) => setEditSubject({...editSubject, name_en: e.target.value})}
                    dir="ltr"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>النصاب الأسبوعي</Label>
                    <Select 
                      value={String(editSubject.weekly_periods || 4)} 
                      onValueChange={(v) => setEditSubject({...editSubject, weekly_periods: parseInt(v)})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[1, 2, 3, 4, 5, 6, 7, 8].map(n => (
                          <SelectItem key={n} value={String(n)}>{n} حصص</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>التصنيف</Label>
                    <Select 
                      value={editSubject.category || 'general'} 
                      onValueChange={(v) => setEditSubject({...editSubject, category: v})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="language">لغات</SelectItem>
                        <SelectItem value="science">علوم</SelectItem>
                        <SelectItem value="islamic">إسلامية</SelectItem>
                        <SelectItem value="technology">تقنية</SelectItem>
                        <SelectItem value="activity">أنشطة</SelectItem>
                        <SelectItem value="social">اجتماعية</SelectItem>
                        <SelectItem value="skills">مهارات</SelectItem>
                        <SelectItem value="general">عام</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditSubjectOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleUpdateSubject} disabled={saving} className="bg-blue-600 hover:bg-blue-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                حفظ التغييرات
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ============================================ */}
        {/* Dialog إضافة قيد جديد */}
        {/* ============================================ */}
        <Dialog open={addConstraintOpen} onOpenChange={setAddConstraintOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Shield className="h-5 w-5 text-rose-600" />
                إضافة قيد إداري جديد
              </DialogTitle>
              <DialogDescription>
                أدخل بيانات القيد الإداري للجدولة
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="constraint-name-ar">اسم القيد *</Label>
                <Input
                  id="constraint-name-ar"
                  value={newConstraint.name_ar}
                  onChange={(e) => setNewConstraint({...newConstraint, name_ar: e.target.value})}
                  placeholder="مثال: منع الحصص المتتالية"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="constraint-desc">وصف القيد</Label>
                <Input
                  id="constraint-desc"
                  value={newConstraint.description_ar}
                  onChange={(e) => setNewConstraint({...newConstraint, description_ar: e.target.value})}
                  placeholder="شرح مختصر للقيد"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>الأولوية</Label>
                  <Select 
                    value={newConstraint.priority} 
                    onValueChange={(v) => setNewConstraint({...newConstraint, priority: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="critical">حرج</SelectItem>
                      <SelectItem value="high">عالي</SelectItem>
                      <SelectItem value="medium">متوسط</SelectItem>
                      <SelectItem value="low">منخفض</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>النوع</Label>
                  <Select 
                    value={newConstraint.type} 
                    onValueChange={(v) => setNewConstraint({...newConstraint, type: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="hard">صارم</SelectItem>
                      <SelectItem value="soft">مرن</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddConstraintOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleAddConstraint} disabled={saving} className="bg-rose-600 hover:bg-rose-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Plus className="h-4 w-4 ml-2" />}
                إضافة
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ============================================ */}
        {/* Dialog تعديل قيد */}
        {/* ============================================ */}
        <Dialog open={editConstraintOpen} onOpenChange={setEditConstraintOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Edit2 className="h-5 w-5 text-blue-600" />
                تعديل القيد الإداري
              </DialogTitle>
            </DialogHeader>
            
            {editConstraint && (
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>اسم القيد *</Label>
                  <Input
                    value={editConstraint.name_ar}
                    onChange={(e) => setEditConstraint({...editConstraint, name_ar: e.target.value})}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>وصف القيد</Label>
                  <Input
                    value={editConstraint.description_ar || ''}
                    onChange={(e) => setEditConstraint({...editConstraint, description_ar: e.target.value})}
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>الأولوية</Label>
                    <Select 
                      value={editConstraint.priority || 'medium'} 
                      onValueChange={(v) => setEditConstraint({...editConstraint, priority: v})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="critical">حرج</SelectItem>
                        <SelectItem value="high">عالي</SelectItem>
                        <SelectItem value="medium">متوسط</SelectItem>
                        <SelectItem value="low">منخفض</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>النوع</Label>
                    <Select 
                      value={editConstraint.type || 'hard'} 
                      onValueChange={(v) => setEditConstraint({...editConstraint, type: v})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="hard">صارم</SelectItem>
                        <SelectItem value="soft">مرن</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditConstraintOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleUpdateConstraint} disabled={saving} className="bg-blue-600 hover:bg-blue-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                حفظ التغييرات
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ============================================ */}
        {/* Dialog إضافة إسناد جديد */}
        {/* ============================================ */}
        <Dialog open={addAssignmentOpen} onOpenChange={setAddAssignmentOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Target className="h-5 w-5 text-indigo-600" />
                إضافة إسناد جديد
              </DialogTitle>
              <DialogDescription>
                ربط معلم بفصل ومادة دراسية
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="assignment-teacher">المعلم *</Label>
                <Select 
                  value={newAssignment.teacher_id} 
                  onValueChange={(v) => setNewAssignment({...newAssignment, teacher_id: v})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="اختر المعلم" />
                  </SelectTrigger>
                  <SelectContent>
                    {teachers.map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.full_name_ar || t.full_name || t.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="assignment-class">الفصل *</Label>
                <Select 
                  value={newAssignment.class_id} 
                  onValueChange={(v) => setNewAssignment({...newAssignment, class_id: v})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="اختر الفصل" />
                  </SelectTrigger>
                  <SelectContent>
                    {classes.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name_ar || c.name || c.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="assignment-subject">المادة *</Label>
                <Select 
                  value={newAssignment.subject_id} 
                  onValueChange={(v) => setNewAssignment({...newAssignment, subject_id: v})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="اختر المادة" />
                  </SelectTrigger>
                  <SelectContent>
                    {/* Use school subjects first, then reference subjects as fallback */}
                    {(subjects.length > 0 ? subjects : referenceSubjects.slice(0, 30)).map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name_ar || s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="assignment-sessions">النصاب الأسبوعي</Label>
                <Select 
                  value={String(newAssignment.weekly_sessions)} 
                  onValueChange={(v) => setNewAssignment({...newAssignment, weekly_sessions: parseInt(v)})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5, 6, 7, 8].map(n => (
                      <SelectItem key={n} value={String(n)}>{n} حصص</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddAssignmentOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleAddAssignment} disabled={saving} className="bg-indigo-600 hover:bg-indigo-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Plus className="h-4 w-4 ml-2" />}
                إضافة
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ============================================ */}
        {/* Dialog تعديل إسناد */}
        {/* ============================================ */}
        <Dialog open={editAssignmentOpen} onOpenChange={setEditAssignmentOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Edit2 className="h-5 w-5 text-blue-600" />
                تعديل الإسناد
              </DialogTitle>
            </DialogHeader>
            
            {editAssignment && (
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>المعلم</Label>
                  <Select 
                    value={editAssignment.teacher_id} 
                    onValueChange={(v) => setEditAssignment({...editAssignment, teacher_id: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {teachers.map((t) => (
                        <SelectItem key={t.id} value={t.id}>
                          {t.full_name_ar || t.full_name || t.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>الفصل</Label>
                  <Select 
                    value={editAssignment.class_id} 
                    onValueChange={(v) => setEditAssignment({...editAssignment, class_id: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {classes.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name_ar || c.name || c.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>المادة</Label>
                  <Select 
                    value={editAssignment.subject_id} 
                    onValueChange={(v) => setEditAssignment({...editAssignment, subject_id: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {/* Use school subjects first, then reference subjects as fallback */}
                      {(subjects.length > 0 ? subjects : referenceSubjects.slice(0, 30)).map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name_ar || s.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>النصاب الأسبوعي</Label>
                  <Select 
                    value={String(editAssignment.weekly_sessions || 4)} 
                    onValueChange={(v) => setEditAssignment({...editAssignment, weekly_sessions: parseInt(v)})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 4, 5, 6, 7, 8].map(n => (
                        <SelectItem key={n} value={String(n)}>{n} حصص</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditAssignmentOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleUpdateAssignment} disabled={saving} className="bg-blue-600 hover:bg-blue-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                حفظ التغييرات
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ================== DIALOG: Edit School Info ================== */}
        <Dialog open={editSchoolInfoOpen} onOpenChange={setEditSchoolInfoOpen}>
          <DialogContent className="max-w-lg" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-brand-navy" />
                تعديل معلومات المدرسة
              </DialogTitle>
              <DialogDescription>
                تحديث المعلومات الأساسية للمدرسة
              </DialogDescription>
            </DialogHeader>
            
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>اسم المدرسة (عربي) *</Label>
                  <Input 
                    value={editedSchoolInfo.name || ''} 
                    onChange={(e) => setEditedSchoolInfo({...editedSchoolInfo, name: e.target.value})}
                    data-testid="school-name-ar"
                  />
                </div>
                <div className="space-y-2">
                  <Label>اسم المدرسة (إنجليزي)</Label>
                  <Input 
                    value={editedSchoolInfo.name_en || ''} 
                    onChange={(e) => setEditedSchoolInfo({...editedSchoolInfo, name_en: e.target.value})}
                    data-testid="school-name-en"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>المدينة</Label>
                  <Input 
                    value={editedSchoolInfo.city || ''} 
                    onChange={(e) => setEditedSchoolInfo({...editedSchoolInfo, city: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <Label>العنوان</Label>
                  <Input 
                    value={editedSchoolInfo.address || ''} 
                    onChange={(e) => setEditedSchoolInfo({...editedSchoolInfo, address: e.target.value})}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>رقم الهاتف</Label>
                  <Input 
                    value={editedSchoolInfo.phone || ''} 
                    onChange={(e) => setEditedSchoolInfo({...editedSchoolInfo, phone: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <Label>البريد الإلكتروني</Label>
                  <Input 
                    type="email"
                    value={editedSchoolInfo.email || ''} 
                    onChange={(e) => setEditedSchoolInfo({...editedSchoolInfo, email: e.target.value})}
                  />
                </div>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditSchoolInfoOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleUpdateSchoolInfo} disabled={saving} className="bg-brand-navy hover:bg-brand-navy/90">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                حفظ التغييرات
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ================== DIALOG: Edit Work Days ================== */}
        <Dialog open={editWorkDaysOpen} onOpenChange={setEditWorkDaysOpen}>
          <DialogContent className="max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-green-600" />
                تعديل أيام العمل
              </DialogTitle>
              <DialogDescription>
                حدد أيام الدراسة وأيام العطلة
              </DialogDescription>
            </DialogHeader>
            
            <div className="py-4">
              <div className="grid grid-cols-7 gap-2">
                {[
                  { key: 'sunday', name: 'الأحد' },
                  { key: 'monday', name: 'الإثنين' },
                  { key: 'tuesday', name: 'الثلاثاء' },
                  { key: 'wednesday', name: 'الأربعاء' },
                  { key: 'thursday', name: 'الخميس' },
                  { key: 'friday', name: 'الجمعة' },
                  { key: 'saturday', name: 'السبت' },
                ].map((day) => (
                  <div 
                    key={day.key}
                    onClick={() => toggleWorkDay(day.key)}
                    className={`p-3 text-center rounded-xl cursor-pointer transition-all border-2 ${
                      editedWorkDays[day.key] 
                        ? 'bg-green-100 border-green-500 text-green-700' 
                        : 'bg-red-50 border-red-200 text-red-600'
                    }`}
                  >
                    <p className="font-bold text-xs">{day.name}</p>
                    <p className="text-[10px] mt-1">
                      {editedWorkDays[day.key] ? 'دراسة' : 'عطلة'}
                    </p>
                  </div>
                ))}
              </div>
              
              <div className="mt-4 p-3 bg-muted rounded-lg text-sm text-muted-foreground">
                <p>أيام الدراسة: {Object.entries(editedWorkDays).filter(([, v]) => v).length}</p>
                <p>أيام العطلة: {Object.entries(editedWorkDays).filter(([, v]) => !v).length}</p>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditWorkDaysOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleSaveWorkDays} disabled={saving} className="bg-green-600 hover:bg-green-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                حفظ التغييرات
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ================== DIALOG: Add Stage ================== */}
        <Dialog open={addStageOpen} onOpenChange={setAddStageOpen}>
          <DialogContent className="max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5 text-purple-600" />
                إضافة مرحلة تعليمية
              </DialogTitle>
            </DialogHeader>
            
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label>اسم المرحلة (عربي) *</Label>
                <Input 
                  value={newStage.name} 
                  onChange={(e) => setNewStage({...newStage, name: e.target.value})}
                  placeholder="مثال: المرحلة الابتدائية"
                />
              </div>
              <div className="space-y-2">
                <Label>اسم المرحلة (إنجليزي)</Label>
                <Input 
                  value={newStage.name_en} 
                  onChange={(e) => setNewStage({...newStage, name_en: e.target.value})}
                  placeholder="Example: Elementary Stage"
                />
              </div>
              <div className="space-y-2">
                <Label>الترتيب</Label>
                <Input 
                  type="number"
                  value={newStage.order} 
                  onChange={(e) => setNewStage({...newStage, order: parseInt(e.target.value) || 1})}
                />
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddStageOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleAddStage} disabled={saving} className="bg-purple-600 hover:bg-purple-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Plus className="h-4 w-4 ml-2" />}
                إضافة
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ================== DIALOG: Edit Stage ================== */}
        <Dialog open={editStageOpen} onOpenChange={setEditStageOpen}>
          <DialogContent className="max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Edit2 className="h-5 w-5 text-purple-600" />
                تعديل مرحلة تعليمية
              </DialogTitle>
            </DialogHeader>
            
            {editStage && (
              <div className="grid gap-4 py-4">
                <div className="space-y-2">
                  <Label>اسم المرحلة (عربي) *</Label>
                  <Input 
                    value={editStage.name || ''} 
                    onChange={(e) => setEditStage({...editStage, name: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <Label>اسم المرحلة (إنجليزي)</Label>
                  <Input 
                    value={editStage.name_en || ''} 
                    onChange={(e) => setEditStage({...editStage, name_en: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <Label>الترتيب</Label>
                  <Input 
                    type="number"
                    value={editStage.order || 1} 
                    onChange={(e) => setEditStage({...editStage, order: parseInt(e.target.value) || 1})}
                  />
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditStageOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleUpdateStage} disabled={saving} className="bg-purple-600 hover:bg-purple-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                حفظ
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ================== DIALOG: Add Grade ================== */}
        <Dialog open={addGradeOpen} onOpenChange={setAddGradeOpen}>
          <DialogContent className="max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <GraduationCap className="h-5 w-5 text-blue-600" />
                إضافة صف دراسي
              </DialogTitle>
            </DialogHeader>
            
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label>المرحلة التعليمية *</Label>
                <Select 
                  value={newGrade.stage_id} 
                  onValueChange={(v) => setNewGrade({...newGrade, stage_id: v})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="اختر المرحلة" />
                  </SelectTrigger>
                  <SelectContent>
                    {stages.map((stage) => (
                      <SelectItem key={stage.id} value={stage.id}>
                        {stage.name_ar || stage.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>اسم الصف (عربي) *</Label>
                <Input 
                  value={newGrade.name} 
                  onChange={(e) => setNewGrade({...newGrade, name: e.target.value})}
                  placeholder="مثال: الصف الأول الابتدائي"
                />
              </div>
              <div className="space-y-2">
                <Label>اسم الصف (إنجليزي)</Label>
                <Input 
                  value={newGrade.name_en} 
                  onChange={(e) => setNewGrade({...newGrade, name_en: e.target.value})}
                  placeholder="Example: Grade 1"
                />
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddGradeOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleAddGrade} disabled={saving} className="bg-blue-600 hover:bg-blue-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Plus className="h-4 w-4 ml-2" />}
                إضافة
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ================== DIALOG: Edit Grade ================== */}
        <Dialog open={editGradeOpen} onOpenChange={setEditGradeOpen}>
          <DialogContent className="max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Edit2 className="h-5 w-5 text-blue-600" />
                تعديل صف دراسي
              </DialogTitle>
            </DialogHeader>
            
            {editGrade && (
              <div className="grid gap-4 py-4">
                <div className="space-y-2">
                  <Label>المرحلة التعليمية *</Label>
                  <Select 
                    value={editGrade.stage_id} 
                    onValueChange={(v) => setEditGrade({...editGrade, stage_id: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {stages.map((stage) => (
                        <SelectItem key={stage.id} value={stage.id}>
                          {stage.name_ar || stage.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>اسم الصف (عربي) *</Label>
                  <Input 
                    value={editGrade.name || ''} 
                    onChange={(e) => setEditGrade({...editGrade, name: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <Label>اسم الصف (إنجليزي)</Label>
                  <Input 
                    value={editGrade.name_en || ''} 
                    onChange={(e) => setEditGrade({...editGrade, name_en: e.target.value})}
                  />
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditGradeOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={handleUpdateGrade} disabled={saving} className="bg-blue-600 hover:bg-blue-700">
                {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                حفظ
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* ================== DIALOG: Delete Confirmation ================== */}
        <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <DialogContent className="max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-600">
                <AlertTriangle className="h-5 w-5" />
                تأكيد الحذف
              </DialogTitle>
              <DialogDescription>
                هذا العنصر مرتبط بعناصر أخرى في النظام
              </DialogDescription>
            </DialogHeader>
            
            <div className="py-4">
              <p className="font-medium mb-2">"{deleteTarget.name}"</p>
              {deleteTarget.dependencies && (
                <div className="p-3 bg-red-50 rounded-lg border border-red-200">
                  <p className="text-sm text-red-700">مرتبط بـ:</p>
                  <ul className="list-disc list-inside text-sm text-red-600 mt-1">
                    {deleteTarget.dependencies.teacher_assignments && (
                      <li>{deleteTarget.dependencies.teacher_assignments} إسناد للمعلمين</li>
                    )}
                    {deleteTarget.dependencies.grades && (
                      <li>{deleteTarget.dependencies.grades} صف دراسي</li>
                    )}
                    {deleteTarget.dependencies.classes && (
                      <li>{deleteTarget.dependencies.classes} فصل</li>
                    )}
                  </ul>
                </div>
              )}
              <p className="text-sm text-muted-foreground mt-3">
                هل أنت متأكد من الحذف؟ هذا الإجراء لا يمكن التراجع عنه.
              </p>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteConfirmOpen(false)}>
                إلغاء
              </Button>
              <Button onClick={confirmDelete} variant="destructive">
                <Trash2 className="h-4 w-4 ml-2" />
                تأكيد الحذف
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}

export { SchoolSettingsPagePro };
