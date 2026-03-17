/**
 * TimetablePageHeader Component
 * رأس صفحة الجدول المدرسي
 * 
 * يعرض عنوان الصفحة وسياق المدرسة الحالي
 */

import React from 'react';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { 
  Calendar, Building2, GraduationCap, Users, Clock, 
  ChevronLeft 
} from 'lucide-react';
import { TimetableStatus, getStatusBadgeStyle, getStatusLabel } from './types';

const TimetablePageHeader = ({ 
  schoolNameAr = '',
  academicYearName = '',
  termName = '',
  totalClasses = 0,
  totalTeachers = 0,
  totalTeachingSlots = 0,
  currentVersionStatus = TimetableStatus.NONE,
  loading = false,
  userName = ''
}) => {
  
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <Skeleton className="w-14 h-14 rounded-2xl" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5].map(i => (
            <Skeleton key={i} className="h-6 w-24 rounded-full" />
          ))}
        </div>
      </div>
    );
  }

  const statusStyle = getStatusBadgeStyle(currentVersionStatus);
  const statusLabel = getStatusLabel(currentVersionStatus);

  return (
    <div className="space-y-4" data-testid="timetable-page-header">
      {/* Main Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Icon */}
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center shadow-lg">
            <Calendar className="h-7 w-7 text-white" />
          </div>
          
          {/* Title & Subtitle */}
          <div>
            <h1 className="font-cairo text-2xl font-bold text-foreground">
              {userName ? `مرحباً، ${userName}` : 'الجدول المدرسي'}
            </h1>
            <div className="flex items-center gap-2 text-base text-muted-foreground">
              <span>الجدول المدرسي</span>
              {schoolNameAr && (
                <>
                  <ChevronLeft className="h-3 w-3" />
                  <span>{schoolNameAr}</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Metadata Chips */}
      <div className="flex flex-wrap items-center gap-2">
        {/* School Name */}
        {schoolNameAr && (
          <Badge variant="outline" className="gap-1.5 py-1 px-2.5 bg-white">
            <Building2 className="h-3.5 w-3.5 text-brand-navy" />
            <span>{schoolNameAr}</span>
          </Badge>
        )}
        
        {/* Academic Year */}
        {academicYearName && (
          <Badge variant="outline" className="gap-1.5 py-1 px-2.5 bg-white">
            <Calendar className="h-3.5 w-3.5 text-blue-600" />
            <span>{academicYearName}</span>
          </Badge>
        )}
        
        {/* Term */}
        {termName && (
          <Badge variant="outline" className="gap-1.5 py-1 px-2.5 bg-white">
            <Clock className="h-3.5 w-3.5 text-purple-600" />
            <span>{termName}</span>
          </Badge>
        )}
        
        {/* Total Classes */}
        <Badge variant="outline" className="gap-1.5 py-1 px-2.5 bg-white">
          <GraduationCap className="h-3.5 w-3.5 text-emerald-600" />
          <span>{totalClasses} فصل</span>
        </Badge>
        
        {/* Total Teachers */}
        <Badge variant="outline" className="gap-1.5 py-1 px-2.5 bg-white">
          <Users className="h-3.5 w-3.5 text-amber-600" />
          <span>{totalTeachers} معلم</span>
        </Badge>
        
        {/* Teaching Slots */}
        {totalTeachingSlots > 0 && (
          <Badge variant="outline" className="gap-1.5 py-1 px-2.5 bg-white">
            <Clock className="h-3.5 w-3.5 text-rose-600" />
            <span>{totalTeachingSlots} حصة</span>
          </Badge>
        )}
        
        {/* Version Status */}
        <Badge className={`gap-1.5 py-1 px-2.5 border ${statusStyle}`}>
          {statusLabel.ar}
        </Badge>
      </div>
    </div>
  );
};

export default TimetablePageHeader;
