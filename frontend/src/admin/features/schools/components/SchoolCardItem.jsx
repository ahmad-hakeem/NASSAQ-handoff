import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  Building2, MapPin, ExternalLink, Eye, Users, GraduationCap, Layers
} from 'lucide-react';
import { SCHOOL_STATUS, getLogoGradient } from '../constants/schoolConstants';

export default function SchoolCardItem({
  school,
  onNavigateDetail,
  onEnterDashboard,
  canEnterDashboard,
  isRTL,
}) {
  const statusCfg = SCHOOL_STATUS[school.status] || SCHOOL_STATUS.active;
  const gradient = getLogoGradient(school.id);

  return (
    <Card
      className="group rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-xl transition-all duration-300 overflow-hidden bg-white dark:bg-slate-900 flex flex-col justify-between hover:border-slate-300 dark:hover:border-slate-700"
      data-testid={`school-card-${school.id}`}
    >
      <div>
        {/* Banner Header with Cohesive Brand Gradient */}
        <div className={`bg-gradient-to-r ${gradient} p-5 text-white relative overflow-hidden`}>
          <div className="absolute inset-0 bg-black/10 pointer-events-none" />
          <div className="relative flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white font-black text-xl shadow-inner shrink-0 border border-white/25">
                {school.name?.charAt(0) || 'م'}
              </div>
              <div className="min-w-0">
                <h3 className="font-cairo font-black text-base leading-snug line-clamp-1 text-white">
                  {school.name}
                </h3>
                <p className="text-xs text-white/85 font-mono mt-0.5 truncate max-w-[180px]">
                  {school.code || school.name_en || '—'}
                </p>
              </div>
            </div>

            <Badge className={`text-[10px] font-bold shrink-0 ${statusCfg.badge} shadow-xs`}>
              {isRTL ? statusCfg.label : statusCfg.label_en}
            </Badge>
          </div>

          <div className="relative flex items-center gap-4 mt-4 text-xs text-white/90 font-medium">
            <span className="flex items-center gap-1.5 truncate">
              <MapPin className="h-3.5 w-3.5 text-white/80 shrink-0" />
              <span className="truncate">{school.city || '—'}</span>
            </span>
            <span className="flex items-center gap-1.5 shrink-0">
              <Building2 className="h-3.5 w-3.5 text-white/80 shrink-0" />
              <span>{school.school_type === 'private' ? (isRTL ? 'أهلية' : 'Private') : (isRTL ? 'حكومية' : 'Public')}</span>
            </span>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="p-4 grid grid-cols-3 gap-2.5 text-center border-b border-slate-100 dark:border-slate-800">
          <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-2xl border border-slate-100 dark:border-slate-800">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-bold mb-0.5 flex items-center justify-center gap-1">
              <GraduationCap className="h-3 w-3 text-sky-500" />
              <span>{isRTL ? 'الطلاب' : 'Students'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.student_count || 0).toLocaleString()}
            </p>
          </div>

          <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-2xl border border-slate-100 dark:border-slate-800">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-bold mb-0.5 flex items-center justify-center gap-1">
              <Users className="h-3 w-3 text-purple-500" />
              <span>{isRTL ? 'المعلمين' : 'Teachers'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.teacher_count || 0).toLocaleString()}
            </p>
          </div>

          <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-2xl border border-slate-100 dark:border-slate-800">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-bold mb-0.5 flex items-center justify-center gap-1">
              <Layers className="h-3 w-3 text-emerald-500" />
              <span>{isRTL ? 'الفصول' : 'Classes'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.class_count || 0).toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="p-4 bg-slate-50/70 dark:bg-slate-900/60 flex items-center justify-between gap-2.5">
        <Button
          variant="outline"
          size="sm"
          className="flex-1 rounded-xl h-10 px-3 font-bold text-xs border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-800 shadow-2xs gap-1.5"
          onClick={() => onNavigateDetail(school.id)}
        >
          <ExternalLink className="h-3.5 w-3.5 text-slate-400" />
          <span>{isRTL ? 'الملف التفصيلي' : 'Details'}</span>
        </Button>

        <Button
          size="sm"
          className="flex-1 rounded-xl h-10 px-4 bg-[#1C3D74] hover:bg-[#152e57] text-white font-black text-xs shadow-md shadow-[#1C3D74]/20 disabled:opacity-40 gap-1.5"
          onClick={() => onEnterDashboard(school)}
          disabled={!canEnterDashboard(school)}
        >
          <Eye className="h-3.5 w-3.5 text-[#46C1BE]" />
          <span>{isRTL ? 'دخول كمدير' : 'Dashboard'}</span>
        </Button>
      </div>
    </Card>
  );
}
