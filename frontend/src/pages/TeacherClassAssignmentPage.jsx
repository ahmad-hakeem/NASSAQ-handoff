/**
 * TeacherClassAssignmentPage
 * صفحة إسناد المعلمين للفصول
 * 
 * تمكن مدير المدرسة من ربط المعلمين بالفصول الدراسية
 * باستخدام السحب والإفلات (Drag & Drop)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DndContext, DragOverlay, useDraggable, useDroppable, closestCenter } from '@dnd-kit/core';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Users, GraduationCap, Search, X, CheckCircle2, AlertCircle,
  ArrowLeft, Trash2, RefreshCw, UserPlus, BookOpen
} from 'lucide-react';

// ============================================
// Draggable Teacher Card
// ============================================
const DraggableTeacher = ({ teacher, isDragging }) => {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: `teacher-${teacher.id}`,
    data: { teacher }
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
      className={`p-3 rounded-lg border-2 bg-white cursor-grab active:cursor-grabbing transition-all ${
        isDragging 
          ? 'border-brand-navy shadow-lg scale-105 opacity-50' 
          : 'border-gray-200 hover:border-brand-navy/50 hover:shadow-md'
      }`}
      data-testid={`teacher-card-${teacher.id}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-navy to-brand-navy/70 flex items-center justify-center text-white font-bold">
          {teacher.full_name?.charAt(0) || 'م'}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm truncate">{teacher.full_name || 'معلم'}</p>
          <p className="text-xs text-muted-foreground truncate">
            {teacher.subjects?.join('، ') || teacher.specialization || 'غير محدد'}
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          {teacher.assignments_count || 0} فصول
        </Badge>
      </div>
    </div>
  );
};

// ============================================
// Droppable Class Box
// ============================================
const DroppableClass = ({ classItem, assignments, onRemoveAssignment, isOver }) => {
  const { setNodeRef, isOver: dropping } = useDroppable({
    id: `class-${classItem.id}`,
    data: { classItem }
  });

  const classAssignments = assignments.filter(a => a.class_id === classItem.id);

  return (
    <div
      ref={setNodeRef}
      className={`p-4 rounded-xl border-2 transition-all ${
        dropping || isOver
          ? 'border-brand-navy bg-brand-navy/5 shadow-md'
          : classAssignments.length > 0
          ? 'border-green-300 bg-green-50/50'
          : 'border-dashed border-amber-300 bg-amber-50/30'
      }`}
      data-testid={`class-box-${classItem.id}`}
    >
      {/* Class Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-lg ${
            classAssignments.length > 0 ? 'bg-green-100' : 'bg-amber-100'
          }`}>
            <GraduationCap className={`h-4 w-4 ${
              classAssignments.length > 0 ? 'text-green-600' : 'text-amber-600'
            }`} />
          </div>
          <div>
            <p className="font-bold text-sm">{classItem.name || 'فصل'}</p>
            <p className="text-xs text-muted-foreground">الشعبة: {classItem.section || '-'}</p>
          </div>
        </div>
        {classAssignments.length > 0 ? (
          <CheckCircle2 className="h-5 w-5 text-green-500" />
        ) : (
          <AlertCircle className="h-5 w-5 text-amber-500" />
        )}
      </div>

      {/* Assigned Teachers */}
      {classAssignments.length > 0 ? (
        <div className="space-y-2">
          {classAssignments.map(assignment => (
            <div
              key={assignment.id}
              className="flex items-center justify-between p-2 bg-white rounded-lg border border-gray-200"
            >
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-brand-navy/10 flex items-center justify-center text-brand-navy font-bold text-sm">
                  {assignment.teacher_name?.charAt(0) || 'م'}
                </div>
                <span className="text-sm font-medium">{assignment.teacher_name}</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-red-500 hover:text-red-700 hover:bg-red-50"
                onClick={() => onRemoveAssignment(assignment.id)}
                data-testid={`remove-assignment-${assignment.id}`}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-4 border-2 border-dashed border-gray-200 rounded-lg">
          <UserPlus className="h-6 w-6 mx-auto text-gray-400 mb-1" />
          <p className="text-xs text-gray-500">اسحب معلم وأفلته هنا</p>
        </div>
      )}
    </div>
  );
};

// ============================================
// Main Page Component
// ============================================
const TeacherClassAssignmentPage = () => {
  const navigate = useNavigate();
  const { api } = useAuth();
  const { nassaqWarning, nassaqError } = useNassaqAlert();
  
  // State
  const [loading, setLoading] = useState(true);
  const [teachers, setTeachers] = useState([]);
  const [classes, setClasses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [searchTeacher, setSearchTeacher] = useState('');
  const [searchClass, setSearchClass] = useState('');
  const [activeTeacher, setActiveTeacher] = useState(null);
  const [saving, setSaving] = useState(false);

  // Load data
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [teachersRes, classesRes, assignmentsRes] = await Promise.all([
        api.get('/teachers'),
        api.get('/classes'),
        api.get('/teacher-class-assignments?page_size=1000')
      ]);

      const assignmentsList = assignmentsRes.data?.data || assignmentsRes.data || [];
      const teachersWithCounts = (teachersRes.data || []).map(t => ({
        ...t,
        assignments_count: assignmentsList.filter(a => a.teacher_id === t.id).length
      }));

      setTeachers(teachersWithCounts);
      setClasses(classesRes.data || []);
      setAssignments(assignmentsList);
    } catch (error) {
      console.error('Error loading data:', error);
      nassaqError('فشل في تحميل البيانات');
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle drag end - create assignment
  const handleDragEnd = async (event) => {
    const { active, over } = event;
    setActiveTeacher(null);

    if (!over || !active) return;

    const teacherId = active.data.current?.teacher?.id;
    const classId = over.data.current?.classItem?.id;

    if (!teacherId || !classId) return;

    // Check if already assigned
    const alreadyAssigned = assignments.some(
      a => a.teacher_id === teacherId && a.class_id === classId
    );

    if (alreadyAssigned) {
      nassaqWarning('هذا المعلم مسند بالفعل لهذا الفصل');
      return;
    }

    setSaving(true);
    try {
      const response = await api.post('/teacher-class-assignments', {
        teacher_id: teacherId,
        class_id: classId
      });

      // Add to local state
      setAssignments(prev => [...prev, response.data.assignment]);
      
      // Update teacher count
      setTeachers(prev => prev.map(t => 
        t.id === teacherId 
          ? { ...t, assignments_count: (t.assignments_count || 0) + 1 }
          : t
      ));

      toast.success('تم إسناد المعلم للفصل بنجاح');
    } catch (error) {
      console.error('Error creating assignment:', error);
      nassaqError(error.response?.data?.detail || 'فشل في إنشاء الإسناد');
    } finally {
      setSaving(false);
    }
  };

  // Handle drag start
  const handleDragStart = (event) => {
    const teacher = event.active.data.current?.teacher;
    if (teacher) {
      setActiveTeacher(teacher);
    }
  };

  // Remove assignment
  const handleRemoveAssignment = async (assignmentId) => {
    const assignment = assignments.find(a => a.id === assignmentId);
    if (!assignment) return;

    setSaving(true);
    try {
      await api.delete(`/teacher-class-assignments/${assignmentId}`);
      
      // Remove from local state
      setAssignments(prev => prev.filter(a => a.id !== assignmentId));
      
      // Update teacher count
      setTeachers(prev => prev.map(t => 
        t.id === assignment.teacher_id 
          ? { ...t, assignments_count: Math.max(0, (t.assignments_count || 1) - 1) }
          : t
      ));

      toast.success('تم حذف الإسناد بنجاح');
    } catch (error) {
      console.error('Error removing assignment:', error);
      nassaqError('فشل في حذف الإسناد');
    } finally {
      setSaving(false);
    }
  };

  // Filter teachers and classes
  const filteredTeachers = teachers.filter(t =>
    t.full_name?.toLowerCase().includes(searchTeacher.toLowerCase()) ||
    t.specialization?.toLowerCase().includes(searchTeacher.toLowerCase())
  );

  const filteredClasses = classes.filter(c =>
    c.name?.toLowerCase().includes(searchClass.toLowerCase()) ||
    c.section?.toLowerCase().includes(searchClass.toLowerCase())
  );

  // Stats
  const assignedClassesCount = new Set(assignments.map(a => a.class_id)).size;
  const unassignedClassesCount = classes.length - assignedClassesCount;

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-muted/30" dir="rtl">
          <div className="p-4 sm:p-6 max-w-7xl mx-auto">
            <Skeleton className="h-10 w-64 mb-6" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Skeleton className="h-[600px]" />
              <Skeleton className="h-[600px]" />
            </div>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-muted/30" dir="rtl">
        <div className="p-4 sm:p-6 max-w-7xl mx-auto" data-testid="teacher-class-assignment-page">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/school/settings')}
                className="mb-2"
              >
                <ArrowLeft className="h-4 w-4 ml-2" />
                العودة للإعدادات
              </Button>
              <h1 className="text-2xl font-bold text-brand-navy flex items-center gap-3">
                <Users className="h-7 w-7" />
                إسناد المعلمين للفصول
              </h1>
              <p className="text-muted-foreground mt-1">
                اسحب المعلم وأفلته على الفصل لإنشاء الإسناد
              </p>
            </div>
            
            <div className="flex items-center gap-4">
              {/* Stats */}
              <div className="flex items-center gap-3">
                <div className="text-center px-4 py-2 bg-green-50 rounded-lg border border-green-200">
                  <p className="text-2xl font-bold text-green-700">{assignedClassesCount}</p>
                  <p className="text-xs text-green-600">فصول مسندة</p>
                </div>
                <div className="text-center px-4 py-2 bg-amber-50 rounded-lg border border-amber-200">
                  <p className="text-2xl font-bold text-amber-700">{unassignedClassesCount}</p>
                  <p className="text-xs text-amber-600">بدون إسناد</p>
                </div>
              </div>
              
              <Button onClick={loadData} variant="outline" disabled={saving}>
                <RefreshCw className={`h-4 w-4 ml-2 ${saving ? 'animate-spin' : ''}`} />
                تحديث
              </Button>
            </div>
          </div>

          {/* Main Content - DnD Context */}
          <DndContext
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Teachers Panel */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Users className="h-5 w-5 text-brand-navy" />
                    المعلمون
                    <Badge variant="outline">{filteredTeachers.length}</Badge>
                  </CardTitle>
                  <div className="relative mt-3">
                    <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="ابحث عن معلم..."
                      value={searchTeacher}
                      onChange={(e) => setSearchTeacher(e.target.value)}
                      className="pr-9"
                    />
                  </div>
                </CardHeader>
                <CardContent className="max-h-[600px] overflow-y-auto space-y-2">
                  {filteredTeachers.length > 0 ? (
                    filteredTeachers.map(teacher => (
                      <DraggableTeacher
                        key={teacher.id}
                        teacher={teacher}
                        isDragging={activeTeacher?.id === teacher.id}
                      />
                    ))
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Users className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>لا يوجد معلمون</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Classes Panel */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <GraduationCap className="h-5 w-5 text-brand-navy" />
                    الفصول الدراسية
                    <Badge variant="outline">{filteredClasses.length}</Badge>
                  </CardTitle>
                  <div className="relative mt-3">
                    <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="ابحث عن فصل..."
                      value={searchClass}
                      onChange={(e) => setSearchClass(e.target.value)}
                      className="pr-9"
                    />
                  </div>
                </CardHeader>
                <CardContent className="max-h-[600px] overflow-y-auto space-y-3">
                  {filteredClasses.length > 0 ? (
                    filteredClasses.map(classItem => (
                      <DroppableClass
                        key={classItem.id}
                        classItem={classItem}
                        assignments={assignments}
                        onRemoveAssignment={handleRemoveAssignment}
                        isOver={false}
                      />
                    ))
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <GraduationCap className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>لا يوجد فصول</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Drag Overlay */}
            <DragOverlay>
              {activeTeacher && (
                <div className="p-3 rounded-lg border-2 border-brand-navy bg-white shadow-xl">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-navy to-brand-navy/70 flex items-center justify-center text-white font-bold">
                      {activeTeacher.full_name?.charAt(0) || 'م'}
                    </div>
                    <div>
                      <p className="font-medium text-sm">{activeTeacher.full_name || 'معلم'}</p>
                      <p className="text-xs text-muted-foreground">جاري النقل...</p>
                    </div>
                  </div>
                </div>
              )}
            </DragOverlay>
          </DndContext>

          {/* Help Section */}
          <Card className="mt-6 bg-blue-50 border-blue-200">
            <CardContent className="py-4">
              <div className="flex items-start gap-3">
                <BookOpen className="h-5 w-5 text-blue-600 mt-0.5" />
                <div>
                  <h4 className="font-medium text-blue-800 mb-1">كيفية الاستخدام</h4>
                  <ul className="text-sm text-blue-700 space-y-1">
                    <li>• اسحب بطاقة المعلم من القائمة اليمنى</li>
                    <li>• أفلتها على صندوق الفصل المراد إسناده</li>
                    <li>• يمكن إسناد نفس المعلم لعدة فصول</li>
                    <li>• اضغط على × لإزالة الإسناد</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </Sidebar>
  );
};

export default TeacherClassAssignmentPage;
