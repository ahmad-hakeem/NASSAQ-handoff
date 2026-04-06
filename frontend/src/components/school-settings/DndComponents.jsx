import { useDraggable, useDroppable } from '@dnd-kit/core';
import { Badge } from '../ui/badge';
import { BookOpen, GraduationCap, RefreshCw, X } from 'lucide-react';

export const DraggableClassItem = ({ classItem, isAssigned, assignedTeacher }) => {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `class-${classItem.id}`,
    data: { classItem }
  });
  
  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
  } : undefined;
  
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={`p-3 rounded-lg border cursor-grab active:cursor-grabbing transition-all
        ${isDragging 
          ? 'opacity-50 border-brand-turquoise bg-brand-turquoise/20 shadow-lg' 
          : isAssigned 
            ? 'bg-green-50 border-green-200' 
            : 'bg-white border-slate-200 hover:border-brand-turquoise hover:shadow-sm'
        }`}
      data-testid={`draggable-class-${classItem.id}`}
    >
      <div className="flex items-center gap-2">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isAssigned ? 'bg-green-100 text-green-600' : 'bg-brand-turquoise/10 text-brand-turquoise'
        }`}>
          <GraduationCap className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-slate-800 truncate text-sm">
            {classItem.name || `${classItem.grade?.name_ar || ''} - ${classItem.section || ''}`}
          </p>
          {isAssigned && assignedTeacher && (
            <p className="text-xs text-green-600 truncate">مسند إلى: {assignedTeacher}</p>
          )}
          {!isAssigned && (
            <p className="text-xs text-slate-500">غير مسند</p>
          )}
        </div>
      </div>
    </div>
  );
};

export const DroppableTeacherBox = ({ teacher, assignments, onRemoveAssignment }) => {
  const { isOver, setNodeRef } = useDroppable({
    id: `teacher-${teacher.id}`,
    data: { teacher }
  });
  
  return (
    <div
      ref={setNodeRef}
      className={`p-3 rounded-xl border-2 transition-all min-h-[120px]
        ${isOver 
          ? 'border-brand-turquoise bg-brand-turquoise/10 shadow-lg' 
          : 'border-slate-200 bg-white hover:border-slate-300'
        }`}
      data-testid={`teacher-drop-zone-${teacher.id}`}
    >
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-100">
        <div className="w-8 h-8 rounded-full bg-brand-navy flex items-center justify-center">
          <span className="text-white font-bold text-xs">
            {(teacher.full_name || teacher.name || '?')[0]}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-slate-800 text-sm truncate">{teacher.full_name || teacher.name || '-'}</p>
          <p className="text-[10px] text-slate-500 truncate">{teacher.specialization || teacher.email || '-'}</p>
        </div>
        <Badge className="bg-brand-navy/10 text-brand-navy text-[10px]">
          {assignments.length}
        </Badge>
      </div>
      
      <div className="space-y-1">
        {assignments.length === 0 ? (
          <div className={`text-center py-3 rounded-lg transition-colors
            ${isOver ? 'bg-brand-turquoise/20' : 'bg-slate-50'}`}
          >
            <p className="text-xs text-slate-400">
              {isOver ? 'أفلت الفصل هنا' : 'لا توجد فصول مسندة'}
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1">
            {assignments.map((assignment) => (
              <div
                key={assignment.id}
                className="flex items-center gap-1 px-2 py-1 rounded-md bg-brand-turquoise/10 border border-brand-turquoise/30 group"
              >
                <span className="text-xs font-medium text-brand-turquoise-dark truncate max-w-[80px]">
                  {assignment.class_name || `فصل ${assignment.class_id?.substring(0, 6)}`}
                </span>
                <button
                  onClick={() => onRemoveAssignment(assignment.id)}
                  className="w-4 h-4 rounded-full bg-red-100 text-red-600 hover:bg-red-200 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  title="إلغاء الإسناد"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export const DraggableSubjectItem = ({ subject, assignedCount }) => {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `subject-${subject.id}`,
    data: { subject }
  });
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined;
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={`p-3 rounded-xl border-2 cursor-grab active:cursor-grabbing transition-all select-none ${
        isDragging
          ? 'opacity-50 border-brand-purple bg-brand-purple/20 shadow-lg scale-95'
          : 'bg-white border-slate-200 hover:border-brand-purple hover:shadow-md'
      }`}
      data-testid={`draggable-subject-${subject.id}`}
    >
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-brand-purple/10 flex items-center justify-center shrink-0">
          <BookOpen className="h-3.5 w-3.5 text-brand-purple" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-slate-800 truncate text-sm">{subject.name_ar}</p>
          <p className="text-xs text-slate-400 truncate">{subject.name_en || subject.category || '—'}</p>
        </div>
        {assignedCount > 0 && (
          <Badge className="bg-brand-purple/10 text-brand-purple border-0 text-xs shrink-0">{assignedCount}</Badge>
        )}
      </div>
    </div>
  );
};

export const DroppableTeacherSubjectBox = ({ teacher, assignments, onRemoveAssignment }) => {
  const { isOver, setNodeRef } = useDroppable({
    id: `teacher-subject-${teacher.id}`,
    data: { teacher }
  });
  return (
    <div
      ref={setNodeRef}
      className={`p-4 rounded-xl border-2 transition-all min-h-[100px] ${
        isOver
          ? 'border-brand-purple bg-brand-purple/10 shadow-lg'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
      data-testid={`teacher-subject-drop-zone-${teacher.id}`}
    >
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-100">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${isOver ? 'bg-brand-purple' : 'bg-brand-navy'}`}>
          <span className="text-white font-bold text-xs">{(teacher.full_name || teacher.name || '?')[0]}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-slate-800 text-sm truncate">{teacher.full_name || teacher.name || '-'}</p>
          <p className="text-xs text-slate-500 truncate">{teacher.specialization || teacher.email || '-'}</p>
        </div>
        <Badge className={`text-xs transition-colors ${isOver ? 'bg-brand-purple/20 text-brand-purple' : 'bg-brand-navy/10 text-brand-navy'}`}>
          {assignments.length} مادة
        </Badge>
      </div>
      <div className="min-h-[40px]">
        {assignments.length === 0 ? (
          <div className={`text-center py-3 rounded-lg transition-colors border-2 border-dashed ${isOver ? 'border-brand-purple bg-brand-purple/5' : 'border-slate-200 bg-slate-50'}`}>
            <p className="text-xs text-slate-400">{isOver ? 'أفلت المادة هنا' : 'لا توجد مواد مسندة'}</p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {assignments.map((assignment) => (
              <div key={assignment.id} className={`flex items-center gap-1 px-2 py-1 rounded-lg border group transition-all ${
                assignment._optimistic ? 'bg-amber-50 border-amber-200 opacity-70' : 'bg-brand-purple/10 border-brand-purple/30 hover:bg-brand-purple/20'
              }`}>
                {assignment._optimistic && <RefreshCw className="h-2.5 w-2.5 text-amber-500 animate-spin shrink-0" />}
                <span className="text-xs font-medium text-brand-purple-dark truncate max-w-[90px]">
                  {assignment.subject_name || assignment.subject_id}
                </span>
                <button
                  onClick={() => onRemoveAssignment(assignment.id)}
                  className="w-4 h-4 rounded-full bg-red-100 text-red-600 hover:bg-red-200 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  title="إلغاء الإسناد"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
