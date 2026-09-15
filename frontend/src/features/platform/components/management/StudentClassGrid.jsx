import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger, DropdownMenuSeparator
} from '@/shared/components/ui/dropdown-menu';
import {
  GraduationCap, MoreHorizontal, Eye, Edit, Key, UserX, UserCheck,
  Trash2, Users, ChevronDown, ChevronUp, GripVertical, ArrowRightLeft,
  BookOpen, Building2, AlertTriangle, Star, Sparkles, Loader2
} from 'lucide-react';

import { useTranslation } from '@/shared/contexts/ThemeContext';
import { useCanViewInternalIds } from '@/shared/hooks/useCanViewInternalIds';
const MALE_AVATAR = (
  <svg viewBox="0 0 40 40" className="w-full h-full">
    <circle cx="20" cy="20" r="20" fill="#E8F4FD" />
    <circle cx="20" cy="16" r="8" fill="#1C3D74" opacity="0.15" />
    <circle cx="20" cy="15" r="6.5" fill="#FDDCB5" />
    <path d="M13.5 13c0-3.5 3-6.5 6.5-6.5s6.5 3 6.5 6.5c0 1-1 1-1 1h-11s-1 0-1-1z" fill="#1C3D74" opacity="0.8" />
    <circle cx="17.5" cy="14.5" r="0.8" fill="#333" />
    <circle cx="22.5" cy="14.5" r="0.8" fill="#333" />
    <path d="M18.5 17.5c0 0 1.5 1.5 3 0" stroke="#E88B7A" strokeWidth="0.6" fill="none" strokeLinecap="round" />
    <path d="M10 32c0-5.5 4.5-10 10-10s10 4.5 10 10" fill="#1C3D74" opacity="0.7" />
    <path d="M16 25l4 2 4-2" stroke="white" strokeWidth="0.8" fill="none" opacity="0.5" />
  </svg>
);

const FEMALE_AVATAR = (
  <svg viewBox="0 0 40 40" className="w-full h-full">
    <circle cx="20" cy="20" r="20" fill="#FDE8F0" />
    <circle cx="20" cy="16" r="8" fill="#615090" opacity="0.15" />
    <circle cx="20" cy="15" r="6.5" fill="#FDDCB5" />
    <path d="M12 14c0-4.5 3.5-8 8-8s8 3.5 8 8c0 0.5-0.3 1-0.8 1h-1.2c0 0 0-3-6-3s-6 3-6 3h-1.2c-0.5 0-0.8-0.5-0.8-1z" fill="#4A3060" opacity="0.85" />
    <circle cx="17.5" cy="14.5" r="0.8" fill="#333" />
    <circle cx="22.5" cy="14.5" r="0.8" fill="#333" />
    <path d="M18.5 17.5c0 0 1.5 1.5 3 0" stroke="#E88B7A" strokeWidth="0.6" fill="none" strokeLinecap="round" />
    <path d="M10 32c0-5.5 4.5-10 10-10s10 4.5 10 10" fill="#615090" opacity="0.6" />
  </svg>
);

const DraggableStudentChip = ({
  student, isRTL, onView, onEdit, onDelete, onAction, canDrag,
  isSelected = false, onToggleSelect
}) => {
  const { t } = useTranslation();
  const canViewInternalIds = useCanViewInternalIds();
  const [isDragging, setIsDragging] = useState(false);

  const handleDragStart = (e) => {
    if (!canDrag) return;
    e.dataTransfer.setData('application/nassaq-student', JSON.stringify({
      id: student.id,
      full_name: student.full_name,
      class_id: student.class_id,
    }));
    e.dataTransfer.effectAllowed = 'move';
    setIsDragging(true);
  };

  const isFemale = student.gender === 'female' || student.gender === 'أنثى';

  return (
    <div
      draggable={canDrag}
      onDragStart={handleDragStart}
      onDragEnd={() => setIsDragging(false)}
      data-testid={`student-chip-${student.id}`}
      data-student-id={student.id}
      data-class-id={student.class_id || ''}
      className={`group flex items-center gap-2 p-2 rounded-xl border transition-all duration-200
        ${isSelected ? 'ring-2 ring-brand-turquoise/70 border-brand-turquoise bg-brand-turquoise/5' : ''}
        ${isDragging ? 'opacity-30 scale-95 border-dashed border-brand-turquoise/50 bg-brand-turquoise/5' : 'border-border/50 bg-white dark:bg-gray-900 hover:shadow-md hover:border-brand-navy/20'}
        ${canDrag ? 'cursor-grab active:cursor-grabbing' : 'cursor-default'}`}
    >
      {onToggleSelect && (
        <input
          type="checkbox"
          aria-label={`تحديد ${student.full_name}`}
          data-testid={`select-student-${student.id}`}
          checked={!!isSelected}
          onChange={(e) => {
            e.stopPropagation();
            onToggleSelect(student.id);
          }}
          onClick={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          className="h-4 w-4 rounded border-gray-300 text-brand-turquoise focus:ring-brand-turquoise/50 cursor-pointer shrink-0"
        />
      )}
      {canDrag && (
        <GripVertical className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-muted-foreground/60 shrink-0 transition-colors" />
      )}
      <div className={`relative w-8 h-8 rounded-full overflow-hidden shrink-0 ring-2 ring-offset-1 ${student.is_gifted ? 'ring-amber-400' : 'ring-brand-navy/10'}`}>
        {isFemale ? FEMALE_AVATAR : MALE_AVATAR}
        {student.is_gifted && (
          <div className="absolute -top-0.5 -end-0.5 w-3.5 h-3.5 rounded-full bg-amber-400 flex items-center justify-center shadow-sm">
            <Star className="h-2 w-2 text-white fill-white" />
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1">
          <p className="text-xs font-semibold truncate leading-tight">{student.full_name}</p>
          {student.is_gifted && (
            <Star className="h-3 w-3 text-amber-500 fill-amber-500 shrink-0" />
          )}
        </div>
        <div className="flex items-center gap-1 min-w-0">
          <p className="text-[10px] text-muted-foreground font-mono truncate">{student.student_number || (canViewInternalIds ? student.id?.slice(0, 8) : '—')}</p>
          {student.talents?.length > 0 && (
            <span className="text-[9px] text-amber-600 dark:text-amber-400 truncate">
              {student.talents.length > 1 ? `+${student.talents.length}` : ''}
            </span>
          )}
        </div>
      </div>
      <Badge variant={student.is_active !== false ? 'default' : 'destructive'}
        className={`text-[9px] h-4 rounded-full border-0 px-1.5 shrink-0 ${student.is_active !== false ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : ''}`}>
        <span className={`w-1 h-1 rounded-full me-0.5 ${student.is_active !== false ? 'bg-emerald-500' : 'bg-red-500'}`} />
        {student.is_active !== false ? (t('active')) : (isRTL ? 'معلق' : 'Off')}
      </Badge>
      <DropdownMenu>
        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
          <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <MoreHorizontal className="h-3.5 w-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44" onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem onClick={() => onView(student)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewProfile')}</DropdownMenuItem>
          <DropdownMenuItem onClick={() => onEdit(student)}><Edit className="h-3.5 w-3.5 me-2" />{t('edit')}</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => onAction(student, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{t('resetPassword2')}</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => onDelete(student)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};

const ClassColumn = ({
  classItem, students, totalStudentCount, isRTL, canDrag, onTransfer,
  onView, onEdit, onDelete, onAction, searchQuery,
  selectedStudentIds, onToggleSelect
}) => {
  const { t } = useTranslation();
  const gradeLabel = classItem.name_ar || classItem.name || '';
  const studentCount = totalStudentCount ?? students.length;
  const PAGE_SIZE = 50;

  const [collapsed, setCollapsed] = useState(false);
  const [visibleStudentCount, setVisibleStudentCount] = useState(PAGE_SIZE);
  const [isDropTarget, setIsDropTarget] = useState(false);
  const dragCounterRef = useRef(0);

  const filteredStudents = useMemo(() => {
    if (!searchQuery) return students;
    const q = searchQuery.toLowerCase();
    return students.filter(s =>
      (s.full_name || '').toLowerCase().includes(q) ||
      (s.student_number || '').toLowerCase().includes(q)
    );
  }, [students, searchQuery]);

  useEffect(() => {
    setVisibleStudentCount(PAGE_SIZE);
  }, [searchQuery, classItem.id]);

  const visibleStudents = filteredStudents.slice(0, visibleStudentCount);
  const hasMoreStudents = visibleStudentCount < filteredStudents.length;

  const handleDragOver = useCallback((e) => {
    if (!canDrag) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, [canDrag]);

  const handleDragEnter = useCallback((e) => {
    if (!canDrag) return;
    e.preventDefault();
    dragCounterRef.current++;
    setIsDropTarget(true);
  }, [canDrag]);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    dragCounterRef.current--;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDropTarget(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDropTarget(false);
    if (!canDrag) return;

    try {
      const raw = e.dataTransfer.getData('application/nassaq-student');
      if (!raw) return;
      const dragData = JSON.parse(raw);
      if (dragData.class_id === classItem.id) return;
      onTransfer(dragData.id, classItem.id, dragData.full_name, classItem.name_ar || classItem.name);
    } catch (err) {
      console.error('Drop error:', err);
    }
  }, [canDrag, classItem, onTransfer]);

  return (
    <div
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      data-testid={`class-column-${classItem.id}`}
      data-class-id={classItem.id}
      data-student-count={studentCount}
      className={`flex flex-col rounded-2xl border-2 transition-all duration-300 overflow-hidden h-fit
        ${isDropTarget
          ? 'border-brand-turquoise bg-brand-turquoise/5 shadow-lg shadow-brand-turquoise/10 scale-[1.01]'
          : 'border-border/40 bg-card hover:border-border/60'}`}
    >
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none border-b border-border/30"
        style={{
          background: isDropTarget
            ? 'linear-gradient(135deg, rgba(70,193,190,0.12) 0%, rgba(28,61,116,0.08) 100%)'
            : 'linear-gradient(135deg, rgba(28,61,116,0.06) 0%, rgba(70,193,190,0.04) 100%)',
        }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 bg-brand-navy/10">
          <Building2 className="h-4.5 w-4.5 text-brand-navy" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-sm truncate">{gradeLabel}</h3>
          <p className="text-[10px] text-muted-foreground">
            {studentCount} {isRTL ? 'طالب' : t('studentsLower')}
            {searchQuery && filteredStudents.length !== students.length && (
              <span className="text-brand-turquoise ms-1">
                ({isRTL ? `${filteredStudents.length} ظاهر` : `${filteredStudents.length} shown`})
              </span>
            )}
          </p>
        </div>
        <Badge variant="outline" className="text-[10px] h-5 rounded-full font-bold shrink-0 bg-brand-navy/5 text-brand-navy border-brand-navy/20">
          {studentCount}
        </Badge>
        {collapsed ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />}
      </div>

      {!collapsed && (
        <div className="p-3 space-y-1.5 max-h-[500px] overflow-y-auto">
          {filteredStudents.length === 0 ? (
            <div className={`text-center py-6 rounded-xl border-2 border-dashed transition-colors
              ${isDropTarget ? 'border-brand-turquoise/40 bg-brand-turquoise/5' : 'border-border/30'}`}>
              <GraduationCap className="h-8 w-8 mx-auto text-muted-foreground/20 mb-2" />
              <p className="text-xs text-muted-foreground/50">
                {searchQuery
                  ? (t('noSearchResults'))
                  : (t('noStudents'))}
              </p>
              {canDrag && !searchQuery && (
                <p className="text-[10px] text-brand-turquoise/60 mt-1">
                  {t('dragAStudentHereToTransfer')}
                </p>
              )}
            </div>
          ) : (
            visibleStudents.map(student => (
              <DraggableStudentChip
                key={student.id}
                student={student}
                isRTL={isRTL}
                canDrag={canDrag}
                onView={onView}
                onEdit={onEdit}
                onDelete={onDelete}
                onAction={onAction}
                isSelected={selectedStudentIds?.has(student.id)}
                onToggleSelect={onToggleSelect}
              />
            ))
          )}
          {hasMoreStudents && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-full mt-2 text-xs"
              data-testid={`show-more-students-${classItem.id}`}
              onClick={() => setVisibleStudentCount((count) => Math.min(count + PAGE_SIZE, filteredStudents.length))}
            >
              {isRTL ? `عرض ${Math.min(PAGE_SIZE, filteredStudents.length - visibleStudentCount)} طالب إضافي` : `Show ${Math.min(PAGE_SIZE, filteredStudents.length - visibleStudentCount)} more`}
            </Button>
          )}
        </div>
      )}
    </div>
  );
};

const UnassignedColumn = ({
  students, isRTL, canDrag, classes, onTransfer,
  onView, onEdit, onDelete, onAction, searchQuery,
  selectedStudentIds, onToggleSelect, onSelectMultiple, onClearMultiple,
  onAutoDistribute, isAutoDistributing = false
}) => {
  const { t } = useTranslation();
  const PAGE_SIZE = 50;
  const [collapsed, setCollapsed] = useState(false);
  const [visibleStudentCount, setVisibleStudentCount] = useState(PAGE_SIZE);
  const [isDropTarget, setIsDropTarget] = useState(false);
  const dragCounterRef = useRef(0);

  const filteredStudents = useMemo(() => {
    if (!searchQuery) return students;
    const q = searchQuery.toLowerCase();
    return students.filter(s =>
      (s.full_name || '').toLowerCase().includes(q) ||
      (s.student_number || '').toLowerCase().includes(q)
    );
  }, [students, searchQuery]);

  useEffect(() => {
    setVisibleStudentCount(PAGE_SIZE);
  }, [searchQuery]);

  const visibleStudents = filteredStudents.slice(0, visibleStudentCount);
  const hasMoreStudents = visibleStudentCount < filteredStudents.length;

  const allUnassignedSelected = useMemo(() => {
    if (filteredStudents.length === 0) return false;
    return filteredStudents.every(s => selectedStudentIds?.has(s.id));
  }, [filteredStudents, selectedStudentIds]);

  const someUnassignedSelected = useMemo(() => {
    if (!selectedStudentIds || selectedStudentIds.size === 0) return false;
    return filteredStudents.some(s => selectedStudentIds.has(s.id));
  }, [filteredStudents, selectedStudentIds]);

  const handleToggleSelectAll = (e) => {
    e.stopPropagation();
    const ids = filteredStudents.map(s => s.id);
    if (allUnassignedSelected) {
      if (onClearMultiple) onClearMultiple(ids);
    } else {
      if (onSelectMultiple) onSelectMultiple(ids);
    }
  };

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    dragCounterRef.current++;
    setIsDropTarget(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    dragCounterRef.current--;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDropTarget(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDropTarget(false);
  }, []);

  if (students.length === 0) return null;

  return (
    <div
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`flex flex-col rounded-2xl border-2 transition-all duration-300 overflow-hidden h-fit
        ${isDropTarget
          ? 'border-amber-400 bg-amber-50/50 shadow-lg'
          : 'border-amber-200/60 bg-amber-50/20 hover:border-amber-300/60'}`}
    >
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none border-b border-amber-200/30"
        style={{ background: 'linear-gradient(135deg, rgba(245,158,11,0.08) 0%, rgba(251,191,36,0.04) 100%)' }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center shrink-0">
          <AlertTriangle className="h-4.5 w-4.5 text-amber-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-sm text-amber-800 truncate">{t('unassigned')}</h3>
            {onSelectMultiple && filteredStudents.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="h-6 px-2 text-[11px] font-bold border-amber-300 bg-white/80 hover:bg-white text-amber-900 shadow-xs"
                onClick={handleToggleSelectAll}
              >
                <input
                  type="checkbox"
                  aria-label={isRTL ? "تحديد جميع الطلاب بدون فصل" : "Select all unassigned"}
                  checked={allUnassignedSelected}
                  ref={el => {
                    if (el) el.indeterminate = !allUnassignedSelected && someUnassignedSelected;
                  }}
                  onChange={() => {}}
                  onClick={(e) => e.stopPropagation()}
                  className="h-3 w-3 me-1 rounded border-amber-400 text-amber-600 focus:ring-amber-500 pointer-events-none"
                />
                {allUnassignedSelected
                  ? (isRTL ? 'إلغاء تحديد الكل' : 'Deselect all')
                  : (isRTL ? `تحديد الكل (${filteredStudents.length})` : `Select all (${filteredStudents.length})`)}
              </Button>
            )}
            {onAutoDistribute && (
              <Button
                variant="default"
                size="sm"
                disabled={isAutoDistributing}
                className="h-6 px-2.5 text-[11px] font-bold bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white shadow-xs gap-1 cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  onAutoDistribute();
                }}
              >
                {isAutoDistributing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                {isRTL ? 'تسكين وتوزيع ذكي' : 'Auto Distribute'}
              </Button>
            )}
          </div>
          <p className="text-[10px] text-amber-600/70">{isRTL ? `${students.length} طالب بدون فصل` : `${students.length} unassigned students`}</p>
        </div>
        <Badge variant="outline" className="text-[10px] h-5 rounded-full font-bold shrink-0 bg-amber-100 text-amber-700 border-amber-300">
          {students.length}
        </Badge>
        {collapsed ? <ChevronDown className="h-4 w-4 text-amber-500 shrink-0" /> : <ChevronUp className="h-4 w-4 text-amber-500 shrink-0" />}
      </div>

      {!collapsed && (
        <div className="p-3 space-y-1.5 max-h-[500px] overflow-y-auto">
           {visibleStudents.map(student => (
            <DraggableStudentChip
              key={student.id}
              student={student}
              isRTL={isRTL}
              canDrag={canDrag}
              onView={onView}
              onEdit={onEdit}
              onDelete={onDelete}
              onAction={onAction}
              isSelected={selectedStudentIds?.has(student.id)}
              onToggleSelect={onToggleSelect}
            />
          ))}
           {hasMoreStudents && (
             <Button
               type="button"
               variant="outline"
               size="sm"
               className="w-full mt-2 text-xs"
               data-testid="show-more-unassigned-students"
               onClick={() => setVisibleStudentCount((count) => Math.min(count + PAGE_SIZE, filteredStudents.length))}
             >
               {isRTL ? `عرض ${Math.min(PAGE_SIZE, filteredStudents.length - visibleStudentCount)} طالب إضافي` : `Show ${Math.min(PAGE_SIZE, filteredStudents.length - visibleStudentCount)} more`}
             </Button>
           )}
        </div>
      )}
    </div>
  );
};

export default function StudentClassGrid({
  students, classes, studentCounts, isRTL, searchQuery,
  onView, onEdit, onDelete, onAction,
  onTransferStudent, onBulkAssign, onBulkDelete,
  onAutoDistribute, isAutoDistributing = false,
  canDrag = false
}) {
  const { t } = useTranslation();
  const [selectedStudentIds, setSelectedStudentIds] = useState(new Set());
  const [bulkTargetClassId, setBulkTargetClassId] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);

  const handleToggleSelect = useCallback((studentId) => {
    setSelectedStudentIds(prev => {
      const next = new Set(prev);
      if (next.has(studentId)) {
        next.delete(studentId);
      } else {
        next.add(studentId);
      }
      return next;
    });
  }, []);

  const handleSelectMultiple = useCallback((ids) => {
    setSelectedStudentIds(prev => {
      const next = new Set(prev);
      ids.forEach(id => next.add(id));
      return next;
    });
  }, []);

  const handleClearMultiple = useCallback((ids) => {
    setSelectedStudentIds(prev => {
      const next = new Set(prev);
      ids.forEach(id => next.delete(id));
      return next;
    });
  }, []);

  const handleClearAllSelection = useCallback(() => {
    setSelectedStudentIds(new Set());
  }, []);

  const handleExecuteBulkAssign = async () => {
    if (!bulkTargetClassId || selectedStudentIds.size === 0) return;

    setBulkLoading(true);
    try {
      if (onBulkAssign) {
        const ok = await onBulkAssign(Array.from(selectedStudentIds), bulkTargetClassId);
        if (ok !== false) {
          setSelectedStudentIds(new Set());
          setBulkTargetClassId('');
        }
      }
    } finally {
      setBulkLoading(false);
    }
  };

  const handleExecuteBulkDelete = async () => {
    if (selectedStudentIds.size === 0) return;
    if (onBulkDelete) {
      onBulkDelete(Array.from(selectedStudentIds));
      setSelectedStudentIds(new Set());
    }
  };

  const classStudentMap = useMemo(() => {
    const map = {};
    const unassigned = [];

    (classes || []).forEach(c => {
      map[c.id] = { classItem: c, students: [] };
    });

    (students || []).forEach(s => {
      if (s.class_id && map[s.class_id]) {
        map[s.class_id].students.push(s);
      } else {
        unassigned.push(s);
      }
    });

    Object.values(map).forEach(entry => {
      entry.students.sort((a, b) => (a.full_name || '').localeCompare(b.full_name || '', 'ar'));
    });
    unassigned.sort((a, b) => (a.full_name || '').localeCompare(b.full_name || '', 'ar'));

    return { map, unassigned };
  }, [students, classes]);

  const sortedClasses = useMemo(() => {
    return Object.values(classStudentMap.map)
      .sort((a, b) => {
        const gA = a.classItem.grade_level || 0;
        const gB = b.classItem.grade_level || 0;
        if (gA !== gB) return gA - gB;
        return (a.classItem.name_ar || a.classItem.name || '').localeCompare(
          b.classItem.name_ar || b.classItem.name || '', 'ar'
        );
      });
  }, [classStudentMap.map]);

  const handleTransfer = useCallback((studentId, targetClassId, studentName, className) => {
    if (onTransferStudent) {
      onTransferStudent(studentId, targetClassId, studentName, className);
    }
  }, [onTransferStudent]);

  if (sortedClasses.length === 0 && classStudentMap.unassigned.length === 0) {
    return (
      <Card className="p-12 text-center border-dashed">
        <GraduationCap className="h-16 w-16 mx-auto text-muted-foreground/15 mb-4" />
        <p className="text-muted-foreground font-medium">{t('noDataAvailable')}</p>
      </Card>
    );
  }

  return (
    <div className="space-y-4 relative pb-16">
      {canDrag && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-brand-turquoise/5 border border-brand-turquoise/20">
          <ArrowRightLeft className="h-4 w-4 text-brand-turquoise shrink-0" />
          <p className="text-xs text-brand-turquoise font-medium">
            {t('dragAndDropStudentsBetweenClassesToTransferThem')}
          </p>
        </div>
      )}

      <UnassignedColumn
        students={classStudentMap.unassigned}
        isRTL={isRTL}
        canDrag={canDrag}
        classes={classes}
        onTransfer={handleTransfer}
        onView={onView}
        onEdit={onEdit}
        onDelete={onDelete}
        onAction={onAction}
        searchQuery={searchQuery}
        selectedStudentIds={selectedStudentIds}
        onToggleSelect={handleToggleSelect}
        onSelectMultiple={handleSelectMultiple}
        onClearMultiple={handleClearMultiple}
        onAutoDistribute={onAutoDistribute}
        isAutoDistributing={isAutoDistributing}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
        {sortedClasses.map(({ classItem, students: classStudents }) => (
          <ClassColumn
            key={classItem.id}
            classItem={classItem}
            students={classStudents}
            totalStudentCount={studentCounts?.get?.(classItem.id)}
            isRTL={isRTL}
            canDrag={canDrag}
            onTransfer={handleTransfer}
            onView={onView}
            onEdit={onEdit}
            onDelete={onDelete}
            onAction={onAction}
            searchQuery={searchQuery}
            selectedStudentIds={selectedStudentIds}
            onToggleSelect={handleToggleSelect}
          />
        ))}
      </div>

      {/* Floating Bulk Actions Bar */}
      {selectedStudentIds.size > 0 && (
        <div className="fixed bottom-6 inset-x-0 z-50 flex justify-center px-4 pointer-events-none animate-in fade-in slide-in-from-bottom-5 duration-200">
          <div className="pointer-events-auto flex flex-wrap items-center gap-3 px-5 py-3 rounded-2xl bg-white/95 dark:bg-gray-900/95 backdrop-blur-md shadow-2xl border border-border/80 text-foreground max-w-3xl w-full justify-between">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="px-3 py-1 font-bold text-xs bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/30">
                {isRTL ? `تم تحديد ${selectedStudentIds.size} طالب` : `${selectedStudentIds.size} students selected`}
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                onClick={handleClearAllSelection}
              >
                {isRTL ? 'إلغاء التحديد' : 'Clear selection'}
              </Button>
            </div>

            <div className="flex items-center gap-2">
              {classes && classes.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <select
                    value={bulkTargetClassId}
                    onChange={(e) => setBulkTargetClassId(e.target.value)}
                    aria-label={isRTL ? "اختر فصلاً للإسناد" : "Select class"}
                    className="h-9 text-xs rounded-xl border border-input bg-background px-3 py-1 text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-turquoise cursor-pointer"
                  >
                    <option value="">{isRTL ? '— اختر فصلاً للإسناد —' : '— Select target class —'}</option>
                    {classes.map((c) => {
                      const classCount = studentCounts?.get?.(c.id)
                        ?? classStudentMap.map[c.id]?.students?.length
                        ?? c.student_count
                        ?? 0;
                      const label = c.name_ar || c.name || `${c.grade_level || ''} ${c.section || ''}`;
                      return (
                        <option key={c.id} value={c.id}>
                          {label} ({classCount} {isRTL ? 'طالب' : t('studentsLower')})
                        </option>
                      );
                    })}
                  </select>

                  <Button
                    size="sm"
                    disabled={!bulkTargetClassId || bulkLoading}
                    className="h-9 px-3 text-xs bg-brand-turquoise hover:bg-brand-turquoise/90 text-white font-medium gap-1.5 shadow-sm cursor-pointer"
                    onClick={handleExecuteBulkAssign}
                  >
                    <ArrowRightLeft className="h-3.5 w-3.5" />
                    {isRTL ? 'إسناد إلى الفصل' : 'Assign to class'}
                  </Button>
                </div>
              )}

              <Button
                variant="destructive"
                size="sm"
                disabled={bulkLoading}
                className="h-9 px-3 text-xs gap-1.5 shadow-sm cursor-pointer"
                onClick={handleExecuteBulkDelete}
              >
                <Trash2 className="h-3.5 w-3.5" />
                {isRTL ? 'حذف المحددين' : 'Delete selected'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
