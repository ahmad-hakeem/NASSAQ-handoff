/**
 * School Settings Page - إعدادات المدرسة
 * NASSAQ | نَسَّق
 * 
 * مقسمة إلى قسمين رئيسيين:
 * 1. البيانات المتغيرة لبناء الجدول (Dynamic Timetable Inputs)
 * 2. البيانات الأساسية الثابتة العامة (Official Static Reference Data)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Separator } from '../components/ui/separator';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  LayoutDashboard, CalendarDays, Clock, School, Users, BookOpen, 
  Sliders, Plus, Edit2, Trash2, Save, CheckCircle2, AlertTriangle,
  AlertCircle, Search, Play, RefreshCw, Info, X, GraduationCap, 
  Target, Settings, Building2, MapPin, Phone, Mail, Globe, Shield,
  Layers, Award, ChevronRight, FileText, Database, Zap, Lock,
  Calendar, Timer, Coffee, Moon, UserX, DoorClosed, Link2, Heart,
  GripVertical, MoveRight, MousePointer, Wand2
} from 'lucide-react';

import { AcademicStructureContent } from './AcademicStructurePage';

// Import dnd-kit for drag and drop
import { DndContext, DragOverlay, closestCenter, useSensor, useSensors, PointerSensor } from '@dnd-kit/core';
import { useDraggable, useDroppable } from '@dnd-kit/core';

// ============================================
// Draggable Class Item Component
// ============================================
const DraggableClassItem = ({ classItem, isAssigned, assignedTeacher }) => {
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

// ============================================
// Droppable Teacher Box Component
// ============================================
const DroppableTeacherBox = ({ teacher, assignments, onRemoveAssignment }) => {
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
      {/* Teacher Header */}
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
      
      {/* Assigned Classes */}
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

// ============================================
// Draggable Subject Item Component
// ============================================
const DraggableSubjectItem = ({ subject, assignedCount }) => {
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

// ============================================
// Droppable Teacher Box For Subjects Component
// ============================================
const DroppableTeacherSubjectBox = ({ teacher, assignments, onRemoveAssignment }) => {
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

// ============================================
// Main Component
// ============================================

function SchoolSettingsPagePro() {
  const navigate = useNavigate();
  const location = useLocation();
  const { api, user } = useAuth();
  const { nassaqWarning, nassaqConfirm, nassaqError } = useNassaqAlert();
  const searchParams = new URLSearchParams(location.search);
  const validSections = ['dynamic', 'academic', 'static'];
  const rawSection = searchParams.get('section') || 'dynamic';
  const initialSection = validSections.includes(rawSection) ? rawSection : 'dynamic';
  const [activeSection, setActiveSectionState] = useState(initialSection);

  const initialTab = searchParams.get('tab') || 'school-info';
  const [activeTab, setActiveTab] = useState(initialTab);

  const setActiveSection = useCallback((section) => {
    setActiveSectionState(section);
    const params = new URLSearchParams(location.search);
    if (section === 'dynamic') {
      params.delete('section');
    } else {
      params.set('section', section);
    }
    const qs = params.toString();
    navigate(`${location.pathname}${qs ? `?${qs}` : ''}`, { replace: true });
  }, [navigate, location.pathname, location.search]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const urlSection = params.get('section') || 'dynamic';
    if (validSections.includes(urlSection) && urlSection !== activeSection) {
      setActiveSectionState(urlSection);
    }
  }, [location.search]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  
  // DnD Sensors for class assignment
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );
  
  // Data States
  const [schoolInfo, setSchoolInfo] = useState({});
  const [settings, setSettings] = useState({});
  const [teachers, setTeachers] = useState([]);
  const [classes, setClasses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [constraints, setConstraints] = useState([]);
  const [readinessData, setReadinessData] = useState(null);
  const [officialCurriculumStats, setOfficialCurriculumStats] = useState(null);
  const [officialStages, setOfficialStages] = useState([]);
  const [officialTracks, setOfficialTracks] = useState([]);
  const [officialRankLoads, setOfficialRankLoads] = useState([]);
  
  // Full curriculum data per stage
  const [stageCurriculums, setStageCurriculums] = useState({});
  const [loadingCurriculum, setLoadingCurriculum] = useState({});
  const [expandedStages, setExpandedStages] = useState({});
  const [expandedTracks, setExpandedTracks] = useState({});
  const [expandedGrades, setExpandedGrades] = useState({});
  
  // Subjects for assignment
  const [subjects, setSubjects] = useState([]);
  const [draggingSubject, setDraggingSubject] = useState(null); // kept for class DnD
  const [selectedSubject, setSelectedSubject] = useState(null); // click-to-select for subject assignment
  const [assignmentSaving, setAssignmentSaving] = useState(false);
  const [assignmentSubTab, setAssignmentSubTab] = useState('subjects'); // 'subjects' or 'classes'
  const [classAssignments, setClassAssignments] = useState([]);
  const [classAssignmentsLoading, setClassAssignmentsLoading] = useState(false);
  const [draggingClass, setDraggingClass] = useState(null);
  
  // Modal States
  const [showEditSchool, setShowEditSchool] = useState(false);
  const [showBreakModal, setShowBreakModal] = useState(false);
  const [showUnavailabilityModal, setShowUnavailabilityModal] = useState(false);
  const [editingBreak, setEditingBreak] = useState(null);
  const [unavailabilityType, setUnavailabilityType] = useState('teacher'); // 'teacher' or 'class'
  
  // Form States
  const [editedSchoolInfo, setEditedSchoolInfo] = useState({});
  
  // Work Days State
  const [workDays, setWorkDays] = useState({
    sunday: true, monday: true, tuesday: true, wednesday: true, thursday: true,
    friday: false, saturday: false
  });
  
  // Timing Settings
  const [timingSettings, setTimingSettings] = useState({
    academicYear: '1446',
    currentSemester: '1',
    dayStart: '07:00',
    dayEnd: '13:15',
    periodsPerDay: 7,
    periodDuration: 45,
    breakDuration: 20,
    breakAfterPeriod: 3
  });
  const [timeSlotsCount, setTimeSlotsCount] = useState(null);
  const [generatingSlots, setGeneratingSlots] = useState(false);
  
  // Break Times
  const [breakTimes, setBreakTimes] = useState([
    { id: 1, name: 'الاستراحة الأولى', afterPeriod: 2, duration: 15, type: 'break' },
    { id: 2, name: 'صلاة الظهر', afterPeriod: 4, duration: 20, type: 'prayer' },
    { id: 3, name: 'الاستراحة الثانية', afterPeriod: 5, duration: 10, type: 'break' }
  ]);
  
  // Unavailability
  const [teacherUnavailability, setTeacherUnavailability] = useState([]);
  const [classUnavailability, setClassUnavailability] = useState([]);
  
  // Hard Constraints (from DB)
  const [hardConstraints, setHardConstraints] = useState([]);
  
  const [softConstraints, setSoftConstraints] = useState([]);
  const [activeHardTab, setActiveHardTab] = useState('all');
  const [activeSoftTab, setActiveSoftTab] = useState('all');

  // ============================================
  // Data Fetching
  // ============================================
  
  const fetchData = useCallback(async () => {
    if (!api) return;
    setLoading(true);
    
    try {
      const [
        settingsRes, teachersRes, classesRes, assignmentsRes, 
        constraintsRes, readinessRes, schoolRes,
        officialStatsRes, officialStagesRes, officialTracksRes, officialRankLoadsRes,
        subjectsRes, hardConstraintsRes, softConstraintsRes
      ] = await Promise.all([
        api.get('/school/settings').catch(() => ({ data: {} })),
        api.get('/teachers').catch(() => ({ data: [] })),
        api.get('/classes').catch(() => ({ data: [] })),
        api.get('/teacher-assignments').catch(() => ({ data: [] })),
        api.get('/school/constraints').catch(() => ({ data: [] })),
        api.get('/timetable-readiness/check').catch(() => ({ data: null })),
        api.get('/school/info').catch(() => ({ data: {} })),
        api.get('/official-curriculum/stats').catch(() => ({ data: null })),
        api.get('/official-curriculum/stages').catch(() => ({ data: [] })),
        api.get('/official-curriculum/tracks').catch(() => ({ data: [] })),
        api.get('/official-curriculum/teacher-rank-loads').catch(() => ({ data: [] })),
        api.get('/school/subjects/unique').catch(() => ({ data: [] })),
        api.get('/school/settings/hard-constraints').catch(() => ({ data: { hard_constraints: [] } })),
        api.get('/school/settings/soft-constraints').catch(() => ({ data: { soft_constraints: [] } }))
      ]);
      
      setSettings(settingsRes.data || {});
      setTeachers(Array.isArray(teachersRes.data) ? teachersRes.data : []);
      setClasses(Array.isArray(classesRes.data) ? classesRes.data : []);
      setAssignments(Array.isArray(assignmentsRes.data) ? assignmentsRes.data : []);
      setConstraints(Array.isArray(constraintsRes.data) ? constraintsRes.data : []);
      setReadinessData(readinessRes.data);
      setSchoolInfo(schoolRes.data || {});
      setOfficialCurriculumStats(officialStatsRes.data);
      setOfficialStages(Array.isArray(officialStagesRes.data) ? officialStagesRes.data : []);
      setOfficialTracks(Array.isArray(officialTracksRes.data) ? officialTracksRes.data : []);
      setOfficialRankLoads(Array.isArray(officialRankLoadsRes.data) ? officialRankLoadsRes.data : []);
      setSubjects(Array.isArray(subjectsRes.data) ? subjectsRes.data : []);
      
      const hcData = hardConstraintsRes.data?.hard_constraints || [];
      setHardConstraints(Array.isArray(hcData) ? hcData : []);

      const scData = softConstraintsRes.data?.soft_constraints || [];
      if (Array.isArray(scData) && scData.length > 0) {
        setSoftConstraints(scData);
      }
      
      // Update states from settings
      const s = settingsRes.data || {};
      if (s.workingDays) {
        setWorkDays({
          sunday: s.workingDays.includes('الأحد'),
          monday: s.workingDays.includes('الإثنين'),
          tuesday: s.workingDays.includes('الثلاثاء'),
          wednesday: s.workingDays.includes('الأربعاء'),
          thursday: s.workingDays.includes('الخميس'),
          friday: s.workingDays.includes('الجمعة'),
          saturday: s.workingDays.includes('السبت')
        });
      }
      
      setTimingSettings({
        academicYear: s.academicYear || '1446',
        currentSemester: s.currentSemester || '1',
        dayStart: s.dayStart || '07:00',
        dayEnd: s.dayEnd || '13:15',
        periodsPerDay: s.periodsPerDay || 7,
        periodDuration: s.periodDuration || 45,
        breakDuration: s.breakDuration || 20,
        breakAfterPeriod: s.breakAfterPeriod || 3
      });

      if (Array.isArray(s.breaks) && s.breaks.length > 0) {
        setBreakTimes(s.breaks.map((b, idx) => ({
          id: b.id || idx + 1,
          name: b.name || 'استراحة',
          afterPeriod: b.afterPeriod || b.after_period || idx + 2,
          duration: b.duration || 15,
          type: b.type || 'break',
        })));
      }
      
      
    } catch (error) {
      console.error('Error fetching data:', error);
      nassaqError('حدث خطأ في تحميل البيانات');
    } finally {
      setLoading(false);
    }
    // Load time slots count separately (non-blocking)
    try {
      const schoolId = user?.tenant_id || user?.school_id || 'SCH-001';
      const res = await api.get(`/time-slots?school_id=${schoolId}`);
      setTimeSlotsCount(Array.isArray(res.data) ? res.data.length : 0);
    } catch { setTimeSlotsCount(0); }
  }, [api, user]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Sync editedSchoolInfo from schoolInfo when it loads
  useEffect(() => {
    if (schoolInfo && Object.keys(schoolInfo).length > 0) {
      setEditedSchoolInfo({
        name_ar: schoolInfo.name_ar || schoolInfo.name || '',
        name_en: schoolInfo.name_en || '',
        type: schoolInfo.type || '',
        stage: schoolInfo.stage || '',
        city: schoolInfo.city || '',
        region: schoolInfo.region || '',
        address: schoolInfo.address || '',
        phone: schoolInfo.phone || '',
        email: schoolInfo.email || '',
        principal_name: schoolInfo.principal_name || '',
      });
    }
  }, [schoolInfo]);

  // ============================================
  // Curriculum Loading Functions
  // ============================================
  
  const fetchStageCurriculum = useCallback(async (stageId) => {
    if (!api || stageCurriculums[stageId] || loadingCurriculum[stageId]) return;
    
    setLoadingCurriculum(prev => ({ ...prev, [stageId]: true }));
    try {
      const response = await api.get(`/official-curriculum/stage/${stageId}/full`);
      setStageCurriculums(prev => ({ ...prev, [stageId]: response.data }));
    } catch (error) {
      console.error('Error fetching stage curriculum:', error);
      nassaqError('حدث خطأ في تحميل بيانات المرحلة');
    } finally {
      setLoadingCurriculum(prev => ({ ...prev, [stageId]: false }));
    }
  }, [api, stageCurriculums, loadingCurriculum]);
  
  const toggleStageExpand = (stageId) => {
    setExpandedStages(prev => {
      const newExpanded = { ...prev, [stageId]: !prev[stageId] };
      if (newExpanded[stageId]) {
        fetchStageCurriculum(stageId);
      }
      return newExpanded;
    });
  };
  
  const toggleTrackExpand = (trackId) => {
    setExpandedTracks(prev => ({ ...prev, [trackId]: !prev[trackId] }));
  };
  
  const toggleGradeExpand = (gradeId) => {
    setExpandedGrades(prev => ({ ...prev, [gradeId]: !prev[gradeId] }));
  };

  // ============================================
  // Save Functions
  // ============================================
  
  const saveAllSettings = async () => {
    setSaving(true);
    try {
      const dayNames = { sunday: 'الأحد', monday: 'الإثنين', tuesday: 'الثلاثاء', wednesday: 'الأربعاء', thursday: 'الخميس', friday: 'الجمعة', saturday: 'السبت' };
      const workingDays = Object.entries(workDays).filter(([_, active]) => active).map(([day]) => dayNames[day]);
      const weekendDays = Object.entries(workDays).filter(([_, active]) => !active).map(([day]) => dayNames[day]);
      
      // Send only the required fields, not the entire settings object
      const dataToSave = {
        academicYear: timingSettings.academicYear,
        currentSemester: timingSettings.currentSemester,
        dayStart: timingSettings.dayStart,
        dayEnd: timingSettings.dayEnd,
        periodsPerDay: timingSettings.periodsPerDay,
        periodDuration: timingSettings.periodDuration,
        breakDuration: timingSettings.breakDuration,
        breakAfterPeriod: timingSettings.breakAfterPeriod,
        workingDays, 
        weekendDays,
        breaks: breakTimes.map(b => ({
          id: b.id,
          name: b.name,
          afterPeriod: b.afterPeriod,
          duration: b.duration,
          type: b.type,
        })),
      };
      
      const res = await api.put('/school/settings', dataToSave);
      const regen = res.data?.time_slots_regenerated;
      if (regen?.regenerated) {
        toast.success(`تم حفظ الإعدادات وإعادة توليد ${regen.count} فترة زمنية`);
        setTimeSlotsCount(regen.count);
      } else {
        toast.success('تم حفظ جميع الإعدادات بنجاح');
      }
      setHasChanges(false);
      api.get('/timetable-readiness/check').then(r => setReadinessData(r.data)).catch(() => {});
    } catch (error) {
      console.error('Save error:', error);
      nassaqError('حدث خطأ في حفظ الإعدادات');
    } finally {
      setSaving(false);
    }
  };
  
  const saveSchoolInfo = async () => {
    setSaving(true);
    try {
      await api.put('/school/info', editedSchoolInfo);
      toast.success('تم حفظ معلومات المدرسة');
      setShowEditSchool(false);
      fetchData();
    } catch (error) {
      nassaqError('حدث خطأ في حفظ معلومات المدرسة');
    } finally {
      setSaving(false);
    }
  };

  const generateTimeSlots = async () => {
    setGeneratingSlots(true);
    try {
      const schoolId = user?.tenant_id || user?.school_id || 'SCH-001';
      const response = await api.post(`/seed/time-slots/${schoolId}`);
      const count = response.data?.count || response.data?.created || 0;
      setTimeSlotsCount(count);
      toast.success(`تم إنشاء ${count} فترة زمنية بنجاح`);
    } catch (error) {
      nassaqError('حدث خطأ أثناء إنشاء الفترات الزمنية');
    } finally {
      setGeneratingSlots(false);
    }
  };

  const fetchTimeSlotsCount = async () => {
    try {
      const schoolId = user?.tenant_id || user?.school_id || 'SCH-001';
      const res = await api.get(`/time-slots?school_id=${schoolId}`);
      setTimeSlotsCount(Array.isArray(res.data) ? res.data.length : 0);
    } catch { setTimeSlotsCount(0); }
  };
  
  // ============================================
  // Teacher Assignment Drag & Drop Functions
  // ============================================
  
  const handleDragStart = (e, subject) => {
    setDraggingSubject(subject);
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('text/plain', subject.id);
  };
  
  const handleDragEnd = () => {
    setDraggingSubject(null);
  };

  // Click-to-select subject, then click teacher to assign
  const handleSelectSubject = (subject) => {
    setSelectedSubject(prev => prev?.id === subject.id ? null : subject);
  };

  const handleAssignToTeacher = async (teacher) => {
    if (!selectedSubject) return;

    const existingAssignment = assignments.find(
      a => a.teacher_id === teacher.id && a.subject_id === selectedSubject.id
    );

    if (existingAssignment) {
      nassaqWarning('هذه المادة مسندة بالفعل لهذا المعلم');
      setSelectedSubject(null);
      return;
    }

    const tempId = `temp-${Date.now()}`;
    const subjectToAssign = selectedSubject;
    const optimisticAssignment = {
      id: tempId,
      teacher_id: teacher.id,
      subject_id: subjectToAssign.id,
      subject_name: subjectToAssign.name_ar,
      school_id: user?.tenant_id || '',
      _optimistic: true,
    };
    setAssignments(prev => [...prev, optimisticAssignment]);
    setSelectedSubject(null);

    try {
      const schoolId = user?.tenant_id || user?.school_id || 'SCH-001';
      const response = await api.post('/teacher-assignments', {
        teacher_id: teacher.id,
        subject_id: subjectToAssign.id,
        school_id: schoolId
      });
      const realId = response.data?.id || response.data?.assignment_id || tempId;
      setAssignments(prev => prev.map(a => a.id === tempId ? { ...a, id: realId, _optimistic: false } : a));
      toast.success(`✓ إسناد "${subjectToAssign.name_ar}" إلى "${teacher.full_name || teacher.name}"`);
    } catch (error) {
      setAssignments(prev => prev.filter(a => a.id !== tempId));
      let errorMessage = 'حدث خطأ في إسناد المادة';
      if (error.response?.data?.detail && typeof error.response.data.detail === 'string') {
        errorMessage = error.response.data.detail;
      }
      nassaqError(errorMessage);
    }
  };

  const removeAssignment = async (assignmentId) => {
    nassaqConfirm('هل أنت متأكد من إلغاء هذا الإسناد؟', async () => {
      const removed = assignments.find(a => a.id === assignmentId);
      setAssignments(prev => prev.filter(a => a.id !== assignmentId));
      try {
        await api.delete(`/teacher-assignments/${assignmentId}`);
        toast.success('تم إلغاء الإسناد');
      } catch (error) {
        if (removed) setAssignments(prev => [...prev, removed]);
        nassaqError('حدث خطأ في إلغاء الإسناد');
      }
    });
  };
  
  const getTeacherAssignments = (teacherId) => {
    return assignments.filter(a => a.teacher_id === teacherId);
  };
  
  const getSubjectById = (subjectId) => {
    return subjects.find(s => s.id === subjectId);
  };
  
  const deleteClass = async (id) => {
    nassaqConfirm('هل أنت متأكد من حذف هذا الفصل؟', async () => {
      try {
        await api.delete(`/classes/${id}`);
        toast.success('تم حذف الفصل بنجاح');
        fetchData();
      } catch (error) {
        console.error('Delete class error:', error);
        let errorMessage = 'حدث خطأ في حذف الفصل';
        if (error.response?.data?.detail) {
          if (typeof error.response.data.detail === 'string') {
            errorMessage = error.response.data.detail;
          }
        }
        nassaqError(errorMessage);
      }
    });
  };
  
  // Track changes
  const handleSettingChange = (key, value) => {
    setTimingSettings(prev => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };
  
  const handleWorkDayChange = (day) => {
    setWorkDays(prev => ({ ...prev, [day]: !prev[day] }));
    setHasChanges(true);
  };
  
  const handleSoftConstraintToggle = async (code) => {
    const c = softConstraints.find(x => x.code === code);
    if (!c) return;
    const newActive = !c.is_active;
    setSoftConstraints(prev => prev.map(x => x.code === code ? { ...x, is_active: newActive } : x));
    try {
      await api.put(`/school/settings/soft-constraints/${code}`, { is_active: newActive });
      toast.success('تم تحديث القيد بنجاح');
    } catch {
      setSoftConstraints(prev => prev.map(x => x.code === code ? { ...x, is_active: !newActive } : x));
      nassaqError('حدث خطأ في تحديث القيد');
    }
  };

  const handleSoftConstraintWeight = async (code, weight) => {
    const prev = softConstraints.find(x => x.code === code)?.weight;
    setSoftConstraints(p => p.map(x => x.code === code ? { ...x, weight } : x));
    try {
      await api.put(`/school/settings/soft-constraints/${code}`, { weight });
    } catch {
      setSoftConstraints(p => p.map(x => x.code === code ? { ...x, weight: prev } : x));
      nassaqError('حدث خطأ في تحديث الأولوية');
    }
  };

  const toggleAllConstraints = async (enable) => {
    setSoftConstraints(prev => prev.map(c => ({ ...c, is_active: enable })));
    try {
      await Promise.all(softConstraints.map(c =>
        api.put(`/school/settings/soft-constraints/${c.code}`, { is_active: enable })
      ));
      toast.success(enable ? 'تم تفعيل جميع القيود' : 'تم تعطيل جميع القيود');
    } catch {
      nassaqError('حدث خطأ في تحديث القيود');
      fetchData();
    }
  };
  
  // Break/Prayer handlers
  const handleAddBreak = () => {
    setEditingBreak(null);
    setShowBreakModal(true);
  };
  
  const handleEditBreak = (breakItem) => {
    setEditingBreak(breakItem);
    setShowBreakModal(true);
  };
  
  const handleDeleteBreak = (breakId) => {
    nassaqConfirm('هل أنت متأكد من حذف هذه الفترة؟', () => {
      setBreakTimes(prev => prev.filter(b => b.id !== breakId));
      setHasChanges(true);
      toast.success('تم حذف الفترة بنجاح');
    }, { title: 'تأكيد الحذف', confirmText: 'نعم، احذف', cancelText: 'إلغاء' });
  };
  
  const handleSaveBreak = (breakData) => {
    if (editingBreak) {
      // Update existing
      setBreakTimes(prev => prev.map(b => b.id === editingBreak.id ? { ...b, ...breakData } : b));
    } else {
      // Add new
      const newBreak = {
        id: Date.now(),
        ...breakData
      };
      setBreakTimes(prev => [...prev, newBreak]);
    }
    setShowBreakModal(false);
    setHasChanges(true);
    toast.success(editingBreak ? 'تم تحديث الفترة بنجاح' : 'تم إضافة الفترة بنجاح');
  };
  
  // Unavailability handlers
  const handleAddUnavailability = (type) => {
    setUnavailabilityType(type);
    setShowUnavailabilityModal(true);
  };
  
  const handleSaveUnavailability = (data) => {
    if (unavailabilityType === 'teacher') {
      setTeacherUnavailability(prev => [...prev, { id: Date.now(), ...data }]);
    } else {
      setClassUnavailability(prev => [...prev, { id: Date.now(), ...data }]);
    }
    setShowUnavailabilityModal(false);
    setHasChanges(true);
    toast.success('تم إضافة فترة عدم التوفر بنجاح');
  };
  
  const handleDeleteUnavailability = (id, type) => {
    nassaqConfirm('هل أنت متأكد من حذف هذه الفترة؟', () => {
      if (type === 'teacher') {
        setTeacherUnavailability(prev => prev.filter(u => u.id !== id));
      } else {
        setClassUnavailability(prev => prev.filter(u => u.id !== id));
      }
      setHasChanges(true);
      toast.success('تم حذف الفترة بنجاح');
    }, { title: 'تأكيد الحذف', confirmText: 'نعم، احذف', cancelText: 'إلغاء' });
  };
  
  // Class Assignment handlers
  const loadClassAssignments = async () => {
    setClassAssignmentsLoading(true);
    try {
      const res = await api.get('/teacher-class-assignments');
      setClassAssignments(res.data || []);
    } catch (error) {
      console.error('Error loading class assignments:', error);
    } finally {
      setClassAssignmentsLoading(false);
    }
  };
  
  const handleCreateClassAssignment = async (teacherId, classId) => {
    try {
      const response = await api.post('/teacher-class-assignments', {
        teacher_id: teacherId,
        class_id: classId
      });
      setClassAssignments(prev => [...prev, response.data.assignment]);
      toast.success('تم إسناد الفصل للمعلم بنجاح');
    } catch (error) {
      nassaqError(error.response?.data?.detail || 'فشل في إنشاء الإسناد');
    }
  };
  
  const handleDeleteClassAssignment = async (assignmentId) => {
    try {
      await api.delete(`/teacher-class-assignments/${assignmentId}`);
      setClassAssignments(prev => prev.filter(a => a.id !== assignmentId));
      toast.success('تم حذف الإسناد بنجاح');
    } catch (error) {
      nassaqError('فشل في حذف الإسناد');
    }
  };
  
  // Load class assignments when tab changes
  useEffect(() => {
    if (assignmentSubTab === 'classes' && classAssignments.length === 0) {
      loadClassAssignments();
    }
  }, [assignmentSubTab]);
  
  // Navigate to specific tab for fixing issues
  const navigateToFix = (category) => {
    setActiveSection('dynamic');
    const tabMapping = {
      'academic_context': 'academic-year',
      'school_days': 'workdays',
      'day_structure': 'timings',
      'classes': 'classes',
      'teachers': 'teacher-assignments',
      'teacher_assignments': 'teacher-assignments',
      'constraints': 'constraints'
    };
    const tab = tabMapping[category] || 'academic-year';
    setActiveTab(tab);
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // ============================================
  // Dynamic Section Tabs Configuration
  // ============================================
  const dynamicTabs = [
    { id: 'school-info', label: 'بيانات المدرسة', icon: Building2 },
    { id: 'academic-year', label: 'العام والفصل الدراسي', icon: Calendar },
    { id: 'workdays', label: 'أيام العمل', icon: CalendarDays },
    { id: 'timings', label: 'التوقيت والحصص', icon: Clock },
    { id: 'breaks', label: 'الاستراحات والصلاة', icon: Coffee },
    { id: 'classes', label: 'الفصول والشعب', icon: School },
    { id: 'teacher-assignments', label: 'إسناد المعلمين', icon: Link2 },
    { id: 'unavailability', label: 'عدم التوفر', icon: UserX },
    { id: 'constraints', label: 'القيود والتفضيلات', icon: Sliders }
  ];
  
  // Static Section Tabs Configuration
  const staticTabs = [
    { id: 'curriculum', label: 'المنهج الرسمي', icon: BookOpen },
    { id: 'stages', label: 'المراحل والمسارات', icon: Layers },
    { id: 'rank-loads', label: 'النصاب التعليمي', icon: Award },
    { id: 'subject-distribution', label: 'توزيع المواد', icon: Target }
  ];

  // ============================================
  // Render
  // ============================================
  
  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-slate-50" dir="rtl">
          <div className="flex items-center justify-center h-screen">
            <div className="text-center">
              <RefreshCw className="h-8 w-8 animate-spin text-[#1C3D74] mx-auto mb-4" />
              <p className="text-slate-600">جاري تحميل البيانات...</p>
            </div>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-slate-50" dir="rtl">
        {/* Main Content */}
        <div className="overflow-auto">
          <div className="max-w-7xl mx-auto p-6 lg:p-8">
          
          {/* Page Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-slate-900">إعدادات المدرسة</h1>
              <p className="text-slate-500 mt-1">إدارة بيانات الجدول والمعلومات المرجعية</p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" onClick={fetchData} disabled={loading} data-testid="refresh-btn">
                <RefreshCw className={`h-4 w-4 ml-2 ${loading ? 'animate-spin' : ''}`} />
                تحديث
              </Button>
              {hasChanges && (
                <Button 
                  onClick={saveAllSettings} 
                  disabled={saving}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white px-6"
                  data-testid="save-all-btn"
                >
                  <Save className="h-4 w-4 ml-2" />
                  {saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                </Button>
              )}
            </div>
          </div>
          
          {/* Readiness Status Card - بطاقة جاهزية الجدول */}
          {readinessData && (
            <Card className="mb-6 overflow-hidden border-0 shadow-lg" data-testid="readiness-card">
              {/* Header Section - Brand Gradient */}
              <div className={`p-5 ${
                readinessData.status === 'FULLY_READY' 
                  ? 'bg-gradient-to-br from-emerald-600 via-emerald-500 to-brand-turquoise' 
                  : readinessData.status === 'PARTIALLY_READY'
                  ? 'bg-gradient-to-br from-brand-navy via-[#2a5096] to-brand-turquoise/80'
                  : 'bg-gradient-to-br from-[#1C3D74] via-[#2a5096] to-brand-turquoise/60'
              } text-white`}>
                <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                  <div className="flex items-center gap-5">
                    {/* Progress Circle */}
                    <div className="relative w-20 h-20 flex-shrink-0">
                      <svg className="w-full h-full transform -rotate-90">
                        <circle cx="40" cy="40" r="34" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="6" />
                        <circle 
                          cx="40" cy="40" r="34" fill="none" stroke="white" strokeWidth="6" strokeLinecap="round"
                          strokeDasharray={`${(readinessData.percentage / 100) * 214} 214`}
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-xl font-bold">{Math.round(readinessData.percentage)}%</span>
                      </div>
                    </div>
                    
                    <div>
                      <h2 className="text-xl font-bold mb-1">
                        {readinessData.status === 'FULLY_READY' ? 'جاهز لإنشاء الجدول!' :
                         readinessData.status === 'PARTIALLY_READY' ? 'بيانات الجدول جاهزة جزئياً' :
                         'بيانات الجدول غير مكتملة'}
                      </h2>
                      <p className="text-white/80 text-sm">
                        {readinessData.summary?.critical_count > 0 && (
                          <span className="flex items-center gap-1">
                            <AlertCircle className="h-4 w-4" />
                            {readinessData.summary.critical_count} عناصر ضرورية مطلوبة لإنشاء الجدول
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  
                  <Button 
                    size="lg"
                    className={`${readinessData.can_generate ? 'bg-white text-[#1C3D74] hover:bg-slate-100' : 'bg-white/20 text-white cursor-not-allowed'}`}
                    disabled={!readinessData.can_generate}
                    onClick={() => navigate('/principal/timetable')}
                    data-testid="generate-timetable-btn"
                  >
                    <Play className="h-5 w-5 ml-2" />
                    {readinessData.can_generate ? 'الذهاب للجدول' : 'أكمل البيانات أولاً'}
                  </Button>
                </div>
              </div>
              
              {/* Required Data Section - البيانات المطلوبة */}
              {readinessData.critical_issues && readinessData.critical_issues.length > 0 && (
                <CardContent className="p-5 bg-white">
                  <div className="mb-4">
                    <h3 className="font-bold text-slate-800 flex items-center gap-2 mb-1">
                      <AlertTriangle className="h-5 w-5 text-amber-500" />
                      البيانات الضرورية المطلوبة
                    </h3>
                    <p className="text-sm text-slate-500">أكمل هذه البيانات لتتمكن من إنشاء الجدول المدرسي</p>
                  </div>
                  
                  <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {/* Group issues by category */}
                    {Object.entries(readinessData.categories || {})
                      .filter(([_, cat]) => cat.status === 'critical')
                      .map(([categoryId, category]) => (
                        <div 
                          key={categoryId}
                          className="p-4 rounded-xl border-2 border-red-200 bg-red-50 hover:border-red-300 transition-all"
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <div className="w-8 h-8 rounded-lg bg-red-500 flex items-center justify-center">
                                <AlertCircle className="h-4 w-4 text-white" />
                              </div>
                              <div>
                                <h4 className="font-bold text-red-800 text-sm">{category.name_ar}</h4>
                                <p className="text-xs text-red-600">{category.score}/{category.max_score} نقطة</p>
                              </div>
                            </div>
                          </div>
                          
                          <ul className="space-y-1 mb-3">
                            {category.issues?.filter(i => i.type === 'critical').slice(0, 2).map((issue, idx) => (
                              <li key={idx} className="text-xs text-red-700 flex items-start gap-1">
                                <X className="h-3 w-3 mt-0.5 flex-shrink-0" />
                                {issue.message_ar}
                              </li>
                            ))}
                          </ul>
                          
                          <Button 
                            size="sm" 
                            className="w-full bg-red-600 hover:bg-red-700 text-white text-xs h-8"
                            onClick={() => navigateToFix(categoryId)}
                            data-testid={`fix-${categoryId}-btn`}
                          >
                            <Edit2 className="h-3 w-3 ml-1" />
                            {category.issues?.[0]?.fix_action || 'إصلاح'}
                          </Button>
                        </div>
                      ))}
                  </div>
                  
                  {/* Ready Categories Summary */}
                  {Object.entries(readinessData.categories || {})
                    .filter(([_, cat]) => cat.status === 'ready').length > 0 && (
                    <div className="mt-4 pt-4 border-t">
                      <h4 className="text-sm font-medium text-slate-600 mb-2 flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                        البيانات المكتملة
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(readinessData.categories || {})
                          .filter(([_, cat]) => cat.status === 'ready')
                          .map(([categoryId, category]) => (
                            <Badge key={categoryId} className="bg-emerald-100 text-emerald-700 gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              {category.name_ar}
                            </Badge>
                          ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              )}
              
              {/* All Ready State */}
              {readinessData.status === 'FULLY_READY' && (
                <CardContent className="p-5 bg-emerald-50">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-8 w-8 text-emerald-600" />
                    <div>
                      <h3 className="font-bold text-emerald-800">جميع البيانات مكتملة!</h3>
                      <p className="text-sm text-emerald-600">يمكنك الآن إنشاء الجدول المدرسي بالذكاء الاصطناعي</p>
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
          )}
          
          {/* Section Toggle - 3 prominent tabs */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <button
              onClick={() => { setActiveSection('dynamic'); setActiveTab('school-info'); }}
              className={`relative group flex items-center gap-3 p-4 rounded-2xl border-2 transition-all duration-300 text-right ${
                activeSection === 'dynamic'
                  ? 'border-[#1C3D74] bg-gradient-to-l from-[#1C3D74] to-[#2a5298] text-white shadow-lg scale-[1.02]'
                  : 'border-slate-200 bg-white hover:border-[#1C3D74]/40 hover:shadow-md'
              }`}
              data-testid="section-dynamic-btn"
            >
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-all ${
                activeSection === 'dynamic' ? 'bg-white/20' : 'bg-[#1C3D74]/10'
              }`}>
                <Zap className={`h-5 w-5 ${activeSection === 'dynamic' ? 'text-white' : 'text-[#1C3D74]'}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className={`font-bold text-sm truncate ${activeSection === 'dynamic' ? 'text-white' : 'text-slate-800'}`}>إعدادات الجدول</p>
                <p className={`text-xs truncate ${activeSection === 'dynamic' ? 'text-white/70' : 'text-slate-400'}`}>التوقيت والحصص والإسناد</p>
              </div>
              {activeSection === 'dynamic' && <div className="absolute -bottom-1.5 right-1/2 translate-x-1/2 w-8 h-1.5 rounded-full bg-white/40" />}
            </button>

            <button
              onClick={() => setActiveSection('academic')}
              className={`relative group flex items-center gap-3 p-4 rounded-2xl border-2 transition-all duration-300 text-right ${
                activeSection === 'academic'
                  ? 'border-teal-600 bg-gradient-to-l from-teal-600 to-teal-700 text-white shadow-lg scale-[1.02]'
                  : 'border-slate-200 bg-white hover:border-teal-400 hover:shadow-md'
              }`}
              data-testid="section-academic-btn"
            >
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-all ${
                activeSection === 'academic' ? 'bg-white/20' : 'bg-teal-600/10'
              }`}>
                <GraduationCap className={`h-5 w-5 ${activeSection === 'academic' ? 'text-white' : 'text-teal-600'}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className={`font-bold text-sm truncate ${activeSection === 'academic' ? 'text-white' : 'text-slate-800'}`}>الهيكل الأكاديمي</p>
                <p className={`text-xs truncate ${activeSection === 'academic' ? 'text-white/70' : 'text-slate-400'}`}>السنة الدراسية والفصول والتقويم</p>
              </div>
              {activeSection === 'academic' && <div className="absolute -bottom-1.5 right-1/2 translate-x-1/2 w-8 h-1.5 rounded-full bg-white/40" />}
            </button>

            <button
              onClick={() => { setActiveSection('static'); setActiveTab('curriculum'); }}
              className={`relative group flex items-center gap-3 p-4 rounded-2xl border-2 transition-all duration-300 text-right ${
                activeSection === 'static'
                  ? 'border-emerald-600 bg-gradient-to-l from-emerald-600 to-emerald-700 text-white shadow-lg scale-[1.02]'
                  : 'border-slate-200 bg-white hover:border-emerald-400 hover:shadow-md'
              }`}
              data-testid="section-static-btn"
            >
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-all ${
                activeSection === 'static' ? 'bg-white/20' : 'bg-emerald-600/10'
              }`}>
                <BookOpen className={`h-5 w-5 ${activeSection === 'static' ? 'text-white' : 'text-emerald-600'}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className={`font-bold text-sm truncate ${activeSection === 'static' ? 'text-white' : 'text-slate-800'}`}>المنهج الرسمي</p>
                <p className={`text-xs truncate ${activeSection === 'static' ? 'text-white/70' : 'text-slate-400'}`}>بيانات وزارة التعليم</p>
              </div>
              {activeSection === 'static' && <div className="absolute -bottom-1.5 right-1/2 translate-x-1/2 w-8 h-1.5 rounded-full bg-white/40" />}
            </button>
          </div>
          
          {/* ========================================= */}
          {/* DYNAMIC SECTION - البيانات المتغيرة */}
          {/* ========================================= */}
          {activeSection === 'dynamic' && (
            <div className="space-y-6">
              {/* Dynamic Tabs - one full row */}
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="w-full h-auto bg-white rounded-2xl p-1.5 shadow-sm border border-slate-200 mb-6 flex flex-row gap-0.5">
                  {dynamicTabs.map((tab) => (
                    <TabsTrigger
                      key={tab.id}
                      value={tab.id}
                      className="flex-1 min-w-0 rounded-xl text-[9px] sm:text-[10px] py-2.5 px-0.5 data-[state=active]:bg-[#1C3D74] data-[state=active]:text-white data-[state=active]:shadow-md transition-all flex flex-col items-center gap-1 text-slate-500 hover:text-slate-700"
                      data-testid={`tab-${tab.id}`}
                    >
                      <tab.icon className="h-3.5 w-3.5 sm:h-4 sm:w-4 flex-shrink-0" />
                      <span className="truncate w-full text-center leading-tight">{tab.label}</span>
                    </TabsTrigger>
                  ))}
                </TabsList>
                
                {/* ======= TAB: بيانات المدرسة الأساسية ======= */}
                <TabsContent value="school-info" className="space-y-6">
                  {/* Header card */}
                  <Card className="bg-white shadow-sm border-[#1C3D74]/20">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-[#1C3D74] flex items-center justify-center">
                            <Building2 className="h-5 w-5 text-white" />
                          </div>
                          <div>
                            <CardTitle className="text-lg text-[#1C3D74]">البيانات الأساسية للمدرسة</CardTitle>
                            <CardDescription>المعلومات الرسمية المعتمدة — تُحفظ في قاعدة البيانات فور الحفظ</CardDescription>
                          </div>
                        </div>
                        {/* Read-only school code badge */}
                        {schoolInfo.license_number && (
                          <Badge className="bg-slate-100 text-slate-600 border border-slate-300 gap-1 text-sm px-3 py-1">
                            <Shield className="h-3 w-3" />
                            رمز المدرسة: {schoolInfo.license_number}
                          </Badge>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Row 1: Arabic name + English name */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="font-semibold text-slate-700 flex items-center gap-1">
                            <Building2 className="h-3.5 w-3.5 text-[#1C3D74]" />
                            اسم المدرسة بالعربية <span className="text-red-500">*</span>
                          </Label>
                          <Input
                            dir="rtl"
                            className="h-11 border-slate-200 focus:border-[#1C3D74] text-right"
                            value={editedSchoolInfo.name_ar || ''}
                            onChange={e => setEditedSchoolInfo(p => ({ ...p, name_ar: e.target.value }))}
                            placeholder="اسم المدرسة بالعربية"
                            data-testid="school-name-ar-input"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="font-semibold text-slate-700 flex items-center gap-1">
                            <Building2 className="h-3.5 w-3.5 text-[#1C3D74]" />
                            School Name (English)
                          </Label>
                          <Input
                            dir="ltr"
                            className="h-11 border-slate-200 focus:border-[#1C3D74]"
                            value={editedSchoolInfo.name_en || ''}
                            onChange={e => setEditedSchoolInfo(p => ({ ...p, name_en: e.target.value }))}
                            placeholder="School name in English"
                            data-testid="school-name-en-input"
                          />
                        </div>
                      </div>

                      {/* Row 2: Type + Stage */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="font-semibold text-slate-700">نوع المدرسة</Label>
                          <Select
                            value={editedSchoolInfo.type || ''}
                            onValueChange={v => setEditedSchoolInfo(p => ({ ...p, type: v }))}
                          >
                            <SelectTrigger className="h-11 border-slate-200" data-testid="school-type-select">
                              <SelectValue placeholder="اختر نوع المدرسة" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="government">حكومية</SelectItem>
                              <SelectItem value="private">أهلية</SelectItem>
                              <SelectItem value="international">دولية</SelectItem>
                              <SelectItem value="special">خاصة</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label className="font-semibold text-slate-700">المرحلة الدراسية</Label>
                          <Select
                            value={editedSchoolInfo.stage || ''}
                            onValueChange={v => setEditedSchoolInfo(p => ({ ...p, stage: v }))}
                          >
                            <SelectTrigger className="h-11 border-slate-200" data-testid="school-stage-select">
                              <SelectValue placeholder="اختر المرحلة" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="primary">ابتدائية</SelectItem>
                              <SelectItem value="middle">متوسطة</SelectItem>
                              <SelectItem value="secondary">ثانوية</SelectItem>
                              <SelectItem value="combined">مشتركة</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      {/* Row 3: City + Region */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="font-semibold text-slate-700 flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5 text-[#1C3D74]" />
                            المدينة
                          </Label>
                          <Input
                            dir="rtl"
                            className="h-11 border-slate-200 focus:border-[#1C3D74] text-right"
                            value={editedSchoolInfo.city || ''}
                            onChange={e => setEditedSchoolInfo(p => ({ ...p, city: e.target.value }))}
                            placeholder="المدينة"
                            data-testid="school-city-input"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="font-semibold text-slate-700 flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5 text-[#1C3D74]" />
                            المنطقة / المحافظة
                          </Label>
                          <Input
                            dir="rtl"
                            className="h-11 border-slate-200 focus:border-[#1C3D74] text-right"
                            value={editedSchoolInfo.region || ''}
                            onChange={e => setEditedSchoolInfo(p => ({ ...p, region: e.target.value }))}
                            placeholder="المنطقة الإدارية"
                            data-testid="school-region-input"
                          />
                        </div>
                      </div>

                      {/* Row 4: Address full */}
                      <div className="space-y-2">
                        <Label className="font-semibold text-slate-700 flex items-center gap-1">
                          <MapPin className="h-3.5 w-3.5 text-[#1C3D74]" />
                          العنوان التفصيلي
                        </Label>
                        <Input
                          dir="rtl"
                          className="h-11 border-slate-200 focus:border-[#1C3D74] text-right"
                          value={editedSchoolInfo.address || ''}
                          onChange={e => setEditedSchoolInfo(p => ({ ...p, address: e.target.value }))}
                          placeholder="الحي، الشارع، رقم المبنى"
                          data-testid="school-address-input"
                        />
                      </div>

                      {/* Row 5: Phone + Email */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="font-semibold text-slate-700 flex items-center gap-1">
                            <Phone className="h-3.5 w-3.5 text-[#1C3D74]" />
                            رقم الهاتف
                          </Label>
                          <Input
                            dir="ltr"
                            type="tel"
                            className="h-11 border-slate-200 focus:border-[#1C3D74]"
                            value={editedSchoolInfo.phone || ''}
                            onChange={e => setEditedSchoolInfo(p => ({ ...p, phone: e.target.value }))}
                            placeholder="+966 1X XXX XXXX"
                            data-testid="school-phone-input"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="font-semibold text-slate-700 flex items-center gap-1">
                            <Mail className="h-3.5 w-3.5 text-[#1C3D74]" />
                            البريد الإلكتروني
                          </Label>
                          <Input
                            dir="ltr"
                            type="email"
                            className="h-11 border-slate-200 focus:border-[#1C3D74]"
                            value={editedSchoolInfo.email || ''}
                            onChange={e => setEditedSchoolInfo(p => ({ ...p, email: e.target.value }))}
                            placeholder="school@example.edu.sa"
                            data-testid="school-email-input"
                          />
                        </div>
                      </div>

                      {/* Row 6: Principal name */}
                      <div className="space-y-2">
                        <Label className="font-semibold text-slate-700 flex items-center gap-1">
                          <Users className="h-3.5 w-3.5 text-[#1C3D74]" />
                          اسم مدير/مديرة المدرسة
                        </Label>
                        <Input
                          dir="rtl"
                          className="h-11 border-slate-200 focus:border-[#1C3D74] text-right"
                          value={editedSchoolInfo.principal_name || ''}
                          onChange={e => setEditedSchoolInfo(p => ({ ...p, principal_name: e.target.value }))}
                          placeholder="الاسم الكامل"
                          data-testid="school-principal-input"
                        />
                      </div>

                      {/* Read-only info strip */}
                      <div className="flex flex-wrap gap-3 pt-2 border-t border-slate-100">
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                          <Shield className="h-3.5 w-3.5" />
                          <span>رمز الترخيص:</span>
                          <span className="font-mono font-semibold text-slate-700">{schoolInfo.license_number || '—'}</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                          <CheckCircle2 className={`h-3.5 w-3.5 ${schoolInfo.is_active ? 'text-emerald-500' : 'text-red-400'}`} />
                          <span>الحالة:</span>
                          <span className={`font-semibold ${schoolInfo.is_active ? 'text-emerald-600' : 'text-red-500'}`}>
                            {schoolInfo.is_active ? 'نشطة' : 'غير نشطة'}
                          </span>
                        </div>
                        {schoolInfo.updated_at && (
                          <div className="flex items-center gap-2 text-sm text-slate-500">
                            <RefreshCw className="h-3.5 w-3.5" />
                            <span>آخر تحديث:</span>
                            <span className="text-slate-600">{new Date(schoolInfo.updated_at).toLocaleDateString('ar-SA')}</span>
                          </div>
                        )}
                      </div>

                      {/* Save button */}
                      <div className="flex justify-end pt-2">
                        <Button
                          onClick={saveSchoolInfo}
                          disabled={saving}
                          className="bg-[#1C3D74] hover:bg-[#152d57] text-white px-8 h-11"
                          data-testid="save-school-info-btn"
                        >
                          {saving ? (
                            <RefreshCw className="h-4 w-4 animate-spin ml-2" />
                          ) : (
                            <Save className="h-4 w-4 ml-2" />
                          )}
                          حفظ بيانات المدرسة
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* ======= TAB: العام والفصل الدراسي ======= */}
                <TabsContent value="academic-year" className="space-y-6">
                  <Card className="bg-white shadow-sm">
                    <CardHeader>
                      <CardTitle className="text-xl flex items-center gap-2">
                        <Calendar className="h-5 w-5 text-[#1C3D74]" />
                        العام والفصل الدراسي الحالي
                      </CardTitle>
                      <CardDescription>حدد العام والفصل الدراسي الذي سيتم بناء الجدول له</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid md:grid-cols-2 gap-6">
                        <div>
                          <Label className="text-sm text-slate-600 mb-2 block">العام الدراسي</Label>
                          <Select 
                            value={timingSettings.academicYear} 
                            onValueChange={(v) => handleSettingChange('academicYear', v)}
                          >
                            <SelectTrigger className="h-12 bg-white" data-testid="academic-year-select">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="1447">1447 هـ</SelectItem>
                              <SelectItem value="1446">1446 هـ</SelectItem>
                              <SelectItem value="1445">1445 هـ</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-sm text-slate-600 mb-2 block">الفصل الدراسي</Label>
                          <Select 
                            value={timingSettings.currentSemester}
                            onValueChange={(v) => handleSettingChange('currentSemester', v)}
                          >
                            <SelectTrigger className="h-12 bg-white" data-testid="semester-select">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="1">الفصل الأول</SelectItem>
                              <SelectItem value="2">الفصل الثاني</SelectItem>
                              <SelectItem value="3">الفصل الثالث</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      
                      <div className="mt-6 flex justify-end">
                        <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-academic-btn">
                          <Save className="h-4 w-4 ml-2" />
                          {saving ? 'جاري الحفظ...' : 'حفظ'}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
                
                {/* ======= TAB: أيام العمل ======= */}
                <TabsContent value="workdays" className="space-y-6">
                  <Card className="bg-white shadow-sm">
                    <CardHeader>
                      <CardTitle className="text-xl flex items-center gap-2">
                        <CalendarDays className="h-5 w-5 text-[#1C3D74]" />
                        أيام العمل والعطلة
                      </CardTitle>
                      <CardDescription>حدد أيام الدراسة الأسبوعية</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-7 gap-3 mb-6">
                        {[
                          { key: 'sunday', ar: 'الأحد', en: 'Sun' },
                          { key: 'monday', ar: 'الإثنين', en: 'Mon' },
                          { key: 'tuesday', ar: 'الثلاثاء', en: 'Tue' },
                          { key: 'wednesday', ar: 'الأربعاء', en: 'Wed' },
                          { key: 'thursday', ar: 'الخميس', en: 'Thu' },
                          { key: 'friday', ar: 'الجمعة', en: 'Fri' },
                          { key: 'saturday', ar: 'السبت', en: 'Sat' }
                        ].map((day) => (
                          <div 
                            key={day.key}
                            onClick={() => handleWorkDayChange(day.key)}
                            className={`cursor-pointer rounded-xl p-4 text-center transition-all duration-200 ${
                              workDays[day.key] 
                                ? 'bg-brand-navy text-white shadow-lg shadow-brand-navy/20' 
                                : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                            }`}
                            data-testid={`day-${day.key}`}
                          >
                            <p className="text-xs mb-1 opacity-70">{day.en}</p>
                            <p className="text-sm font-bold">{day.ar}</p>
                            <div className="mt-2">
                              {workDays[day.key] ? <CheckCircle2 className="h-4 w-4 mx-auto" /> : <X className="h-4 w-4 mx-auto opacity-50" />}
                            </div>
                          </div>
                        ))}
                      </div>
                      
                      <Separator className="my-6" />
                      
                      <div className="flex items-center justify-between">
                        <div className="flex gap-6">
                          <div className="flex items-center gap-2">
                            <div className="w-4 h-4 rounded-full bg-brand-navy"></div>
                            <span className="text-sm text-slate-600">{Object.values(workDays).filter(Boolean).length} أيام دراسة</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-4 h-4 rounded-full bg-slate-200"></div>
                            <span className="text-sm text-slate-600">{Object.values(workDays).filter(v => !v).length} أيام عطلة</span>
                          </div>
                        </div>
                        <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-workdays-btn">
                          <Save className="h-4 w-4 ml-2" />
                          {saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
                
                {/* ======= TAB: التوقيت والحصص ======= */}
                <TabsContent value="timings" className="space-y-6">
                  <Card className="bg-white shadow-sm">
                    <CardHeader>
                      <CardTitle className="text-xl flex items-center gap-2">
                        <Clock className="h-5 w-5 text-[#1C3D74]" />
                        إعدادات التوقيت والحصص
                      </CardTitle>
                      <CardDescription>حدد هيكل اليوم الدراسي وعدد الحصص</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid md:grid-cols-2 gap-6">
                        <div className="space-y-4">
                          <div>
                            <Label className="text-sm text-slate-600 mb-2 block flex items-center gap-1.5">
                              <Clock className="h-3.5 w-3.5 text-[#1C3D74]" />
                              وقت بداية اليوم الدراسي
                            </Label>
                            <div className="flex items-center gap-2" data-testid="day-start-input">
                              {/* Hour selector */}
                              <Select
                                value={timingSettings.dayStart?.split(':')[0] || '07'}
                                onValueChange={(h) => {
                                  const m = timingSettings.dayStart?.split(':')[1] || '00';
                                  handleSettingChange('dayStart', `${h}:${m}`);
                                }}
                              >
                                <SelectTrigger className="h-12 w-24 text-lg font-bold text-center border-[#1C3D74]/30 focus:border-[#1C3D74]">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {['05','06','07','08','09','10','11','12'].map(h => (
                                    <SelectItem key={h} value={h} className="text-lg font-bold text-center">
                                      {h}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <span className="text-2xl font-bold text-slate-400 select-none">:</span>
                              {/* Minute selector */}
                              <Select
                                value={timingSettings.dayStart?.split(':')[1] || '00'}
                                onValueChange={(m) => {
                                  const h = timingSettings.dayStart?.split(':')[0] || '07';
                                  handleSettingChange('dayStart', `${h}:${m}`);
                                }}
                              >
                                <SelectTrigger className="h-12 w-24 text-lg font-bold text-center border-[#1C3D74]/30 focus:border-[#1C3D74]">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {['00','05','10','15','20','25','30','35','40','45','50','55'].map(m => (
                                    <SelectItem key={m} value={m} className="text-lg font-bold text-center">
                                      {m}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <span className="text-sm text-slate-500 mr-1">صباحاً</span>
                            </div>
                          </div>
                          <div>
                            <Label className="text-sm text-slate-600 mb-2 block">عدد الحصص في اليوم</Label>
                            <Select 
                              value={String(timingSettings.periodsPerDay)}
                              onValueChange={(v) => handleSettingChange('periodsPerDay', parseInt(v))}
                            >
                              <SelectTrigger className="h-12" data-testid="periods-per-day-select">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[5, 6, 7, 8, 9, 10].map(n => <SelectItem key={n} value={String(n)}>{n} حصص</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <div className="space-y-4">
                          <div>
                            <Label className="text-sm text-slate-600 mb-2 block">مدة الحصة (بالدقائق)</Label>
                            <Select 
                              value={String(timingSettings.periodDuration)}
                              onValueChange={(v) => handleSettingChange('periodDuration', parseInt(v))}
                            >
                              <SelectTrigger className="h-12" data-testid="period-duration-select">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[30, 35, 40, 45, 50, 55, 60].map(n => <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-sm text-slate-600 mb-2 block">مدة الاستراحة الأساسية (بالدقائق)</Label>
                            <Select 
                              value={String(timingSettings.breakDuration)}
                              onValueChange={(v) => handleSettingChange('breakDuration', parseInt(v))}
                            >
                              <SelectTrigger className="h-12" data-testid="break-duration-select">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[10, 15, 20, 25, 30].map(n => <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      </div>
                      
                      {/* Timing Summary */}
                      <div className="mt-6 p-4 bg-slate-50 rounded-xl">
                        <h4 className="font-medium text-slate-700 mb-3">ملخص اليوم الدراسي</h4>
                        <div className="grid grid-cols-4 gap-4">
                          <div className="text-center p-3 bg-white rounded-lg">
                            <p className="text-sm text-slate-500">بداية اليوم</p>
                            <p className="text-xl font-bold text-[#1C3D74]">{timingSettings.dayStart}</p>
                          </div>
                          <div className="text-center p-3 bg-white rounded-lg">
                            <p className="text-sm text-slate-500">عدد الحصص</p>
                            <p className="text-xl font-bold text-[#1C3D74]">{timingSettings.periodsPerDay}</p>
                          </div>
                          <div className="text-center p-3 bg-white rounded-lg">
                            <p className="text-sm text-slate-500">مدة الحصة</p>
                            <p className="text-xl font-bold text-[#1C3D74]">{timingSettings.periodDuration} د</p>
                          </div>
                          <div className="text-center p-3 bg-white rounded-lg">
                            <p className="text-sm text-slate-500">الاستراحة</p>
                            <p className="text-xl font-bold text-[#1C3D74]">{timingSettings.breakDuration} د</p>
                          </div>
                        </div>
                      </div>
                      
                      <div className="mt-6 flex justify-end">
                        <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-timings-btn">
                          <Save className="h-4 w-4 ml-2" />
                          {saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Time Slots Generation Card */}
                  <Card className="bg-white shadow-sm">
                    <CardContent className="p-5">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${timeSlotsCount > 0 ? 'bg-emerald-100' : 'bg-amber-100'}`}>
                            <Timer className={`h-6 w-6 ${timeSlotsCount > 0 ? 'text-emerald-600' : 'text-amber-600'}`} />
                          </div>
                          <div>
                            <h3 className="font-bold text-slate-800">الفترات الزمنية للجدول</h3>
                            <p className="text-sm text-slate-500 mt-0.5">
                              {timeSlotsCount === null
                                ? 'جاري التحقق...'
                                : timeSlotsCount === 0
                                ? 'لا توجد فترات زمنية — اضغط "توليد" لإنشائها تلقائياً من إعدادات التوقيت'
                                : `${timeSlotsCount} فترة زمنية مُعرَّفة للجدول`
                              }
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {timeSlotsCount > 0 && (
                            <Badge className="bg-emerald-100 text-emerald-700 border-0">
                              <CheckCircle2 className="h-3 w-3 ml-1" />
                              جاهز
                            </Badge>
                          )}
                          <Button
                            onClick={generateTimeSlots}
                            disabled={generatingSlots}
                            variant={timeSlotsCount > 0 ? 'outline' : 'default'}
                            className={timeSlotsCount > 0 ? '' : 'bg-[#1C3D74] hover:bg-[#152d57]'}
                            data-testid="generate-time-slots-btn"
                          >
                            {generatingSlots ? (
                              <RefreshCw className="h-4 w-4 ml-2 animate-spin" />
                            ) : (
                              <Wand2 className="h-4 w-4 ml-2" />
                            )}
                            {timeSlotsCount > 0 ? 'إعادة توليد' : 'توليد الفترات'}
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
                
                {/* ======= TAB: الاستراحات والصلاة ======= */}
                <TabsContent value="breaks" className="space-y-6">
                  <Card className="bg-white shadow-sm">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="text-xl flex items-center gap-2">
                            <Coffee className="h-5 w-5 text-[#1C3D74]" />
                            فترات الاستراحة والصلاة
                          </CardTitle>
                          <CardDescription>حدد أوقات الاستراحات وفترات الصلاة</CardDescription>
                        </div>
                        <Button variant="outline" className="gap-2" onClick={handleAddBreak} data-testid="add-break-btn">
                          <Plus className="h-4 w-4" />
                          إضافة فترة
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {breakTimes.map((breakTime) => (
                          <div key={breakTime.id} className={`flex items-center justify-between p-4 rounded-xl border ${
                            breakTime.type === 'prayer' ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'
                          }`}>
                            <div className="flex items-center gap-4">
                              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                                breakTime.type === 'prayer' ? 'bg-emerald-500 text-white' : 'bg-amber-500 text-white'
                              }`}>
                                {breakTime.type === 'prayer' ? <Moon className="h-5 w-5" /> : <Coffee className="h-5 w-5" />}
                              </div>
                              <div>
                                <p className="font-medium">{breakTime.name}</p>
                                <p className="text-sm text-slate-500">بعد الحصة {breakTime.afterPeriod} • {breakTime.duration} دقيقة</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button variant="ghost" size="sm" onClick={() => handleEditBreak(breakTime)} data-testid={`edit-break-${breakTime.id}`}>
                                <Edit2 className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="sm" className="text-red-500" onClick={() => handleDeleteBreak(breakTime.id)} data-testid={`delete-break-${breakTime.id}`}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                      
                      <div className="mt-6 flex justify-end">
                        <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-breaks-btn">
                          <Save className="h-4 w-4 ml-2" />
                          {saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
                
                {/* ======= TAB: الفصول والشعب ======= */}
                <TabsContent value="classes" className="space-y-6">
                  <Card className="bg-white shadow-sm border-brand-navy/10">
                    <CardHeader className="bg-gradient-to-l from-brand-navy/5 to-transparent">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 rounded-xl bg-brand-navy flex items-center justify-center">
                            <School className="h-6 w-6 text-white" />
                          </div>
                          <div>
                            <CardTitle className="text-xl text-brand-navy">الفصول الدراسية والشعب</CardTitle>
                            <CardDescription className="text-brand-navy/60">{classes.length} فصل مسجل في قاعدة البيانات</CardDescription>
                          </div>
                        </div>
                        <Badge variant="outline" className="bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/30">
                          <Database className="h-3 w-3 ml-1" />
                          بيانات من قاعدة البيانات
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="p-0">
                      {classes.length === 0 ? (
                        <div className="text-center py-12">
                          <School className="h-16 w-16 text-slate-200 mx-auto mb-4" />
                          <p className="text-lg text-slate-500 mb-2">لا يوجد فصول مسجلة</p>
                          <p className="text-sm text-slate-400">يمكنك إضافة الفصول من صفحة إدارة المستخدمين والفصول</p>
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full">
                            <thead className="bg-slate-50">
                              <tr>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-brand-navy">#</th>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-brand-navy">اسم الفصل</th>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-brand-navy">الصف</th>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-brand-navy">الشعبة</th>
                                <th className="text-center py-3 px-4 text-sm font-semibold text-brand-navy">السعة</th>
                                <th className="text-center py-3 px-4 text-sm font-semibold text-brand-navy">الحالة</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {classes.map((cls, idx) => (
                                <tr key={cls.id || idx} className="hover:bg-brand-navy/5 transition-colors">
                                  <td className="py-3 px-4 text-slate-500 text-sm">{idx + 1}</td>
                                  <td className="py-3 px-4">
                                    <span className="font-medium text-slate-800">{cls.name || cls.name_ar || '-'}</span>
                                  </td>
                                  <td className="py-3 px-4 text-slate-600">{cls.grade_level || cls.grade || cls.grade_name || '-'}</td>
                                  <td className="py-3 px-4 text-slate-600">{cls.section || '-'}</td>
                                  <td className="py-3 px-4 text-center">
                                    <Badge variant="outline" className="bg-brand-navy/5 text-brand-navy border-brand-navy/20">
                                      {cls.capacity || 30} طالب
                                    </Badge>
                                  </td>
                                  <td className="py-3 px-4 text-center">
                                    <Badge className={cls.is_active !== false ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}>
                                      {cls.is_active !== false ? 'نشط' : 'غير نشط'}
                                    </Badge>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                      {/* Info Banner */}
                      <div className="p-4 bg-amber-50 border-t border-amber-200">
                        <div className="flex items-start gap-3">
                          <Info className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
                          <div>
                            <p className="text-sm text-amber-700">
                              لإضافة أو تعديل الفصول، استخدم صفحة <span className="font-medium">إدارة المستخدمين والفصول</span> من القائمة الجانبية.
                            </p>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
                
                {/* ======= TAB: إسناد المعلمين ======= */}
                <TabsContent value="teacher-assignments" className="space-y-6">
                  {/* Sub-Tab Selector */}
                  <div className="grid grid-cols-2 gap-4">
                    <button
                      onClick={() => setAssignmentSubTab('subjects')}
                      className={`p-4 rounded-xl border-2 transition-all ${
                        assignmentSubTab === 'subjects'
                          ? 'border-brand-purple bg-brand-purple/5 shadow-md'
                          : 'border-slate-200 bg-white hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          assignmentSubTab === 'subjects' ? 'bg-brand-purple text-white' : 'bg-slate-100 text-slate-500'
                        }`}>
                          <BookOpen className="h-5 w-5" />
                        </div>
                        <div className="text-right">
                          <h4 className={`font-bold ${assignmentSubTab === 'subjects' ? 'text-brand-purple' : 'text-slate-700'}`}>
                            إسناد المواد
                          </h4>
                          <p className="text-xs text-slate-500">{assignments.length} إسناد</p>
                        </div>
                      </div>
                    </button>
                    
                    <button
                      onClick={() => setAssignmentSubTab('classes')}
                      className={`p-4 rounded-xl border-2 transition-all ${
                        assignmentSubTab === 'classes'
                          ? 'border-brand-turquoise bg-brand-turquoise/5 shadow-md'
                          : 'border-slate-200 bg-white hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          assignmentSubTab === 'classes' ? 'bg-brand-turquoise text-white' : 'bg-slate-100 text-slate-500'
                        }`}>
                          <GraduationCap className="h-5 w-5" />
                        </div>
                        <div className="text-right">
                          <h4 className={`font-bold ${assignmentSubTab === 'classes' ? 'text-brand-turquoise-dark' : 'text-slate-700'}`}>
                            إسناد الفصول
                          </h4>
                          <p className="text-xs text-slate-500">{classAssignments.length} إسناد</p>
                        </div>
                      </div>
                    </button>
                  </div>
                  
                  {/* ===== إسناد المواد ===== */}
                  {assignmentSubTab === 'subjects' && (
                    <DndContext
                      sensors={sensors}
                      collisionDetection={closestCenter}
                      onDragStart={(e) => setDraggingSubject(e.active?.data?.current?.subject || null)}
                      onDragEnd={(e) => {
                        setDraggingSubject(null);
                        const subject = e.active?.data?.current?.subject;
                        const teacher = e.over?.data?.current?.teacher;
                        if (subject && teacher) {
                          const existingAssignment = assignments.find(
                            a => a.teacher_id === teacher.id && a.subject_id === subject.id
                          );
                          if (existingAssignment) {
                            nassaqWarning('هذه المادة مسندة بالفعل لهذا المعلم');
                          } else {
                            // Optimistic update
                            const tempId = `temp-${Date.now()}`;
                            const optimistic = {
                              id: tempId, teacher_id: teacher.id, subject_id: subject.id,
                              subject_name: subject.name_ar, school_id: user?.tenant_id || '', _optimistic: true,
                            };
                            setAssignments(prev => [...prev, optimistic]);
                            const schoolId = user?.tenant_id || user?.school_id || 'SCH-001';
                            api.post('/teacher-assignments', { teacher_id: teacher.id, subject_id: subject.id, school_id: schoolId })
                              .then(res => {
                                const realId = res.data?.id || res.data?.assignment_id || tempId;
                                setAssignments(prev => prev.map(a => a.id === tempId ? { ...a, id: realId, _optimistic: false } : a));
                                toast.success(`✓ إسناد "${subject.name_ar}" إلى "${teacher.full_name || teacher.name}"`);
                              })
                              .catch(err => {
                                setAssignments(prev => prev.filter(a => a.id !== tempId));
                                nassaqError(err.response?.data?.detail || 'حدث خطأ في إسناد المادة');
                              });
                          }
                        }
                      }}
                    >
                  {/* Header Card */}
                  <Card className="bg-gradient-to-l from-brand-purple/10 to-brand-purple/5 border-brand-purple/20">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-brand-purple flex items-center justify-center">
                            <BookOpen className="h-5 w-5 text-white" />
                          </div>
                          <div>
                            <h3 className="text-lg font-bold text-brand-purple">ربط المعلمين بالمواد</h3>
                            <p className="text-xs text-brand-purple/60">
                              {teachers.length} معلم • {subjects.length} مادة • {assignments.length} إسناد
                            </p>
                          </div>
                        </div>
                        <Badge variant="outline" className="bg-brand-purple/10 text-brand-purple border-brand-purple/30 text-xs">
                          <Zap className="h-3 w-3 ml-1" />
                          سحب وإفلات
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Instructions */}
                  <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
                    <div className="flex items-start gap-2">
                      <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                      <p className="text-xs text-blue-700">
                        اسحب أي مادة من قائمة المواد على اليسار وأفلتها داخل صندوق المعلم المطلوب لإسنادها له.
                        يمكنك إسناد نفس المادة لأكثر من معلم. يتم الحفظ تلقائياً.
                      </p>
                    </div>
                  </div>
                  
                  {/* Main Grid - Drag & Drop */}
                  <div className="grid lg:grid-cols-5 gap-4">
                    {/* Subjects List (Draggable) */}
                    <div className="lg:col-span-2">
                      <Card className="bg-white shadow-sm h-full">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base flex items-center gap-2 text-brand-purple">
                            <BookOpen className="h-4 w-4" />
                            المواد الدراسية
                            <Badge variant="outline" className="text-xs">{subjects.length}</Badge>
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <ScrollArea className="h-[420px] pr-2">
                            <div className="space-y-2">
                              {subjects.map((subject) => {
                                const assignedCount = assignments.filter(a => a.subject_id === subject.id).length;
                                return (
                                  <DraggableSubjectItem
                                    key={subject.id}
                                    subject={subject}
                                    assignedCount={assignedCount}
                                  />
                                );
                              })}
                            </div>
                          </ScrollArea>
                        </CardContent>
                      </Card>
                    </div>

                    {/* Teachers List (Droppable) */}
                    <div className="lg:col-span-3">
                      <Card className="bg-white shadow-sm h-full">
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-base flex items-center gap-2 text-brand-navy">
                              <Users className="h-4 w-4" />
                              المعلمون
                              <Badge variant="outline" className="text-xs">{teachers.length}</Badge>
                            </CardTitle>
                            {assignments.length > 0 && (
                              <Badge variant="outline" className="text-brand-purple border-brand-purple/30">
                                {assignments.length} إسناد
                              </Badge>
                            )}
                          </div>
                        </CardHeader>
                        <CardContent>
                          <ScrollArea className="h-[420px] pr-2">
                            {teachers.length === 0 ? (
                              <div className="text-center py-12">
                                <Users className="h-16 w-16 text-slate-200 mx-auto mb-4" />
                                <p className="text-slate-500">لا يوجد معلمين مسجلين</p>
                              </div>
                            ) : (
                              <div className="grid grid-cols-2 gap-3">
                                {teachers.map((teacher) => {
                                  const teacherAssignments = getTeacherAssignments(teacher.id);
                                  return (
                                    <DroppableTeacherSubjectBox
                                      key={teacher.id}
                                      teacher={teacher}
                                      assignments={teacherAssignments}
                                      onRemoveAssignment={removeAssignment}
                                    />
                                  );
                                })}
                              </div>
                            )}
                          </ScrollArea>
                        </CardContent>
                      </Card>
                    </div>
                  </div>

                  {/* Drag Overlay */}
                  <DragOverlay>
                    {draggingSubject ? (
                      <div className="p-3 rounded-xl border-2 border-brand-purple bg-brand-purple text-white shadow-2xl opacity-95 min-w-[140px]">
                        <div className="flex items-center gap-2">
                          <BookOpen className="h-4 w-4 text-white shrink-0" />
                          <span className="text-sm font-bold truncate">{draggingSubject.name_ar}</span>
                        </div>
                      </div>
                    ) : null}
                  </DragOverlay>
                    </DndContext>
                  )}
                  
                  {/* ===== إسناد الفصول ===== */}
                  {assignmentSubTab === 'classes' && (
                    <DndContext 
                      sensors={sensors}
                      collisionDetection={closestCenter}
                      onDragStart={(e) => setDraggingClass(e.active?.data?.current?.classItem || null)}
                      onDragEnd={(e) => {
                        setDraggingClass(null);
                        const classItem = e.active?.data?.current?.classItem;
                        const teacher = e.over?.data?.current?.teacher;
                        if (classItem && teacher) {
                          // Check if already assigned
                          const exists = classAssignments.some(a => a.class_id === classItem.id && a.teacher_id === teacher.id);
                          if (!exists) {
                            handleCreateClassAssignment(teacher.id, classItem.id);
                          } else {
                            nassaqWarning('هذا الفصل مسند بالفعل لهذا المعلم');
                          }
                        }
                      }}
                    >
                      {/* Header */}
                      <Card className="bg-gradient-to-l from-brand-turquoise/10 to-brand-turquoise/5 border-brand-turquoise/20">
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-xl bg-brand-turquoise flex items-center justify-center">
                                <GraduationCap className="h-5 w-5 text-white" />
                              </div>
                              <div>
                                <h3 className="text-lg font-bold text-brand-turquoise-dark">ربط المعلمين بالفصول</h3>
                                <p className="text-xs text-slate-600">
                                  {teachers.length} معلم • {classes.length} فصل • {classAssignments.length} إسناد
                                </p>
                              </div>
                            </div>
                            <Badge variant="outline" className="bg-brand-turquoise/10 text-brand-turquoise-dark border-brand-turquoise/30 text-xs">
                              <Zap className="h-3 w-3 ml-1" />
                              سحب وإفلات
                            </Badge>
                          </div>
                          <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs text-blue-700">
                            <span className="font-bold">الإعداد الافتراضي:</span> جميع المعلمين مرتبطون بجميع الفصول تلقائيًا. يمكنك إزالة فصل من كارت المعلم لإلغاء الربط.
                          </div>
                        </CardContent>
                      </Card>
                      
                      {/* Instructions */}
                      <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
                        <div className="flex items-start gap-2">
                          <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                          <p className="text-xs text-blue-700">
                            اسحب أي فصل من قائمة الفصول على اليسار وأفلته داخل صندوق المعلم المطلوب لإسناده له.
                            يتم الحفظ تلقائياً في قاعدة البيانات ويُستخدم في توليد الجدول.
                          </p>
                        </div>
                      </div>
                      
                      {/* Main Grid - Drag & Drop */}
                      <div className="grid lg:grid-cols-5 gap-4">
                        {/* Classes List (Draggable) */}
                        <div className="lg:col-span-2">
                          <Card className="bg-white shadow-sm h-full">
                            <CardHeader className="pb-2">
                              <CardTitle className="text-base flex items-center gap-2">
                                <GraduationCap className="h-4 w-4 text-brand-turquoise" />
                                الفصول الدراسية
                                <Badge variant="outline" className="text-xs">{classes.length}</Badge>
                              </CardTitle>
                            </CardHeader>
                            <CardContent>
                              <ScrollArea className="h-[400px] pr-2">
                                <div className="space-y-2">
                                  {classes.map((classItem) => {
                                    const hasAssignment = classAssignments.some(a => a.class_id === classItem.id);
                                    return (
                                      <DraggableClassItem 
                                        key={classItem.id} 
                                        classItem={classItem}
                                        isAssigned={hasAssignment}
                                        assignedTeacher={classAssignments.find(a => a.class_id === classItem.id)?.teacher_name}
                                      />
                                    );
                                  })}
                                </div>
                              </ScrollArea>
                            </CardContent>
                          </Card>
                        </div>
                        
                        {/* Teachers List (Droppable) */}
                        <div className="lg:col-span-3">
                          <Card className="bg-white shadow-sm h-full">
                            <CardHeader className="pb-2">
                              <CardTitle className="text-base flex items-center gap-2">
                                <Users className="h-4 w-4 text-brand-navy" />
                                المعلمون
                                <Badge variant="outline" className="text-xs">{teachers.length}</Badge>
                              </CardTitle>
                            </CardHeader>
                            <CardContent>
                              <ScrollArea className="h-[400px] pr-2">
                                <div className="grid grid-cols-2 gap-3">
                                  {teachers.map((teacher) => {
                                    const teacherClassAssignments = classAssignments.filter(a => a.teacher_id === teacher.id);
                                    return (
                                      <DroppableTeacherBox
                                        key={teacher.id}
                                        teacher={teacher}
                                        assignments={teacherClassAssignments}
                                        onRemoveAssignment={handleDeleteClassAssignment}
                                      />
                                    );
                                  })}
                                </div>
                              </ScrollArea>
                            </CardContent>
                          </Card>
                        </div>
                      </div>
                      
                      {/* Stats */}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="p-3 bg-green-50 rounded-xl border border-green-200 text-center">
                          <p className="text-2xl font-bold text-green-700">{new Set(classAssignments.map(a => a.class_id)).size}</p>
                          <p className="text-xs text-green-600">فصول مسندة</p>
                        </div>
                        <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-center">
                          <p className="text-2xl font-bold text-amber-700">{classes.length - new Set(classAssignments.map(a => a.class_id)).size}</p>
                          <p className="text-xs text-amber-600">بدون إسناد</p>
                        </div>
                        <div className="p-3 bg-blue-50 rounded-xl border border-blue-200 text-center">
                          <p className="text-2xl font-bold text-blue-700">{classAssignments.length}</p>
                          <p className="text-xs text-blue-600">إجمالي الإسنادات</p>
                        </div>
                      </div>
                      
                      {/* Drag Overlay */}
                      <DragOverlay>
                        {draggingClass && (
                          <div className="p-3 rounded-lg border-2 border-brand-turquoise bg-white shadow-xl">
                            <div className="flex items-center gap-2">
                              <GraduationCap className="h-5 w-5 text-brand-turquoise" />
                              <div>
                                <p className="font-medium text-sm">{draggingClass.name}</p>
                                <p className="text-xs text-muted-foreground">{draggingClass.section}</p>
                              </div>
                            </div>
                          </div>
                        )}
                      </DragOverlay>
                    </DndContext>
                  )}
                </TabsContent>
                
                {/* ======= TAB: عدم التوفر ======= */}
                <TabsContent value="unavailability" className="space-y-6">
                  <div className="grid md:grid-cols-2 gap-6">
                    {/* Teacher Unavailability */}
                    <Card className="bg-white shadow-sm">
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <div>
                            <CardTitle className="text-lg flex items-center gap-2">
                              <UserX className="h-5 w-5 text-amber-600" />
                              عدم توفر المعلمين
                            </CardTitle>
                            <CardDescription>حدد أوقات عدم توفر المعلمين</CardDescription>
                          </div>
                          <Button variant="outline" size="sm" className="gap-1" onClick={() => handleAddUnavailability('teacher')} data-testid="add-teacher-unavailability-btn">
                            <Plus className="h-4 w-4" />
                            إضافة
                          </Button>
                        </div>
                      </CardHeader>
                      <CardContent>
                        {teacherUnavailability.length === 0 ? (
                          <div className="text-center py-8 text-slate-400">
                            <UserX className="h-10 w-10 mx-auto mb-2 opacity-50" />
                            <p className="text-sm">لا يوجد قيود على توفر المعلمين</p>
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {teacherUnavailability.map((item) => (
                              <div key={item.id} className="flex items-center justify-between p-3 bg-amber-50 rounded-lg border border-amber-200">
                                <span className="text-sm">{item.teacher_name} - {item.day} - الحصة {item.period}</span>
                                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-red-500" onClick={() => handleDeleteUnavailability(item.id, 'teacher')}><X className="h-3 w-3" /></Button>
                              </div>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                    
                    {/* Class Unavailability */}
                    <Card className="bg-white shadow-sm">
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <div>
                            <CardTitle className="text-lg flex items-center gap-2">
                              <DoorClosed className="h-5 w-5 text-red-600" />
                              عدم توفر الفصول
                            </CardTitle>
                            <CardDescription>حدد أوقات عدم توفر الفصول</CardDescription>
                          </div>
                          <Button variant="outline" size="sm" className="gap-1" onClick={() => handleAddUnavailability('class')} data-testid="add-class-unavailability-btn">
                            <Plus className="h-4 w-4" />
                            إضافة
                          </Button>
                        </div>
                      </CardHeader>
                      <CardContent>
                        {classUnavailability.length === 0 ? (
                          <div className="text-center py-8 text-slate-400">
                            <DoorClosed className="h-10 w-10 mx-auto mb-2 opacity-50" />
                            <p className="text-sm">لا يوجد قيود على توفر الفصول</p>
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {classUnavailability.map((item) => (
                              <div key={item.id} className="flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-200">
                                <span className="text-sm">{item.class_name} - {item.day} - الحصة {item.period}</span>
                                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-red-500" onClick={() => handleDeleteUnavailability(item.id, 'class')}><X className="h-3 w-3" /></Button>
                              </div>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                </TabsContent>
                
                {/* ======= TAB: القيود والتفضيلات ======= */}
                <TabsContent value="constraints" className="space-y-0">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                    {/* ===== النصف الأول: القيود الإلزامية (Hard Constraints) ===== */}
                    <div className="flex flex-col">
                      <div className="bg-gradient-to-br from-red-50 to-rose-50 border-2 border-red-200 rounded-2xl overflow-hidden flex flex-col h-full">
                        <div className="p-4 border-b border-red-200 bg-white/60">
                          <div className="flex items-center gap-2.5 mb-1.5">
                            <div className="w-9 h-9 rounded-xl bg-red-500 flex items-center justify-center shadow-sm">
                              <Shield className="h-4.5 w-4.5 text-white" />
                            </div>
                            <div className="flex-1">
                              <h3 className="text-base font-bold text-red-800">القيود الإلزامية</h3>
                              <p className="text-[11px] text-red-500 mt-0.5">Hard Constraints</p>
                            </div>
                            <Badge className="bg-red-100 text-red-700 border border-red-200 text-xs">
                              {hardConstraints.length} قيد
                            </Badge>
                          </div>
                          <p className="text-xs text-red-600/80 flex items-center gap-1.5 mt-2">
                            <Lock className="h-3.5 w-3.5" />
                            قيود نظامية ثابتة لا يمكن خرقها — مطبقة تلقائياً
                          </p>
                        </div>

                        {(() => {
                          const hardCategoryLabels = {
                            all: { label: 'الكل', color: 'red' },
                            resource_conflict: { label: 'تعارض الموارد', color: 'red' },
                            time_boundary: { label: 'حدود الوقت', color: 'orange' },
                            capacity: { label: 'السعة', color: 'blue' },
                            workload: { label: 'نصاب العمل', color: 'purple' },
                            curriculum: { label: 'المنهج', color: 'green' },
                            distribution: { label: 'التوزيع', color: 'teal' },
                            assignment: { label: 'الإسناد', color: 'indigo' },
                            completeness: { label: 'الاكتمال', color: 'emerald' },
                            data_integrity: { label: 'صحة البيانات', color: 'slate' },
                            publishing: { label: 'النشر', color: 'amber' }
                          };
                          const hardGrouped = {};
                          hardConstraints.forEach(c => {
                            const cat = c.category || 'other';
                            if (!hardGrouped[cat]) hardGrouped[cat] = [];
                            hardGrouped[cat].push(c);
                          });
                          const hardCats = Object.keys(hardGrouped);
                          const filteredHard = activeHardTab === 'all' ? hardConstraints : (hardGrouped[activeHardTab] || []);

                          return (
                            <>
                              <div className="flex flex-wrap gap-1.5 p-3 border-b border-red-100 bg-white/40">
                                {['all', ...hardCats].map(cat => {
                                  const info = hardCategoryLabels[cat] || { label: cat, color: 'slate' };
                                  const count = cat === 'all' ? hardConstraints.length : (hardGrouped[cat]?.length || 0);
                                  return (
                                    <button
                                      key={cat}
                                      onClick={() => setActiveHardTab(cat)}
                                      className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all font-medium ${
                                        activeHardTab === cat
                                          ? 'bg-red-500 text-white border-red-500 shadow-sm'
                                          : 'bg-white text-slate-600 border-slate-200 hover:border-red-300 hover:text-red-600'
                                      }`}
                                    >
                                      {info.label} ({count})
                                    </button>
                                  );
                                })}
                              </div>
                              <div className="flex-1 overflow-y-auto p-3 space-y-2" style={{ maxHeight: '520px' }}>
                                {filteredHard.length === 0 ? (
                                  <div className="text-center py-8 text-slate-400">
                                    <Shield className="h-10 w-10 mx-auto mb-2 opacity-40" />
                                    <p className="text-sm">{hardConstraints.length === 0 ? 'لا توجد قيود إلزامية' : 'لا توجد قيود في هذا التصنيف'}</p>
                                  </div>
                                ) : (
                                  filteredHard.map(c => {
                                    const catInfo = hardCategoryLabels[c.category] || { label: c.category, color: 'slate' };
                                    const bgColors = {
                                      red: 'bg-red-50/80 border-red-200', orange: 'bg-orange-50/80 border-orange-200',
                                      blue: 'bg-blue-50/80 border-blue-200', purple: 'bg-purple-50/80 border-purple-200',
                                      green: 'bg-green-50/80 border-green-200', teal: 'bg-teal-50/80 border-teal-200',
                                      indigo: 'bg-indigo-50/80 border-indigo-200', emerald: 'bg-emerald-50/80 border-emerald-200',
                                      slate: 'bg-slate-50/80 border-slate-200', amber: 'bg-amber-50/80 border-amber-200'
                                    };
                                    return (
                                      <div key={c.code} className={`flex items-start gap-2.5 p-3 rounded-xl border ${bgColors[catInfo.color] || bgColors.slate}`}>
                                        <div className="w-7 h-7 rounded-lg bg-white border flex items-center justify-center shadow-sm flex-shrink-0 mt-0.5">
                                          <Lock className="h-3.5 w-3.5 text-red-500" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                          <div className="flex items-center gap-2 mb-0.5">
                                            <span className="text-[10px] font-mono bg-white/60 px-1.5 py-0.5 rounded border text-slate-500">{c.code}</span>
                                            <span className="text-sm font-semibold text-slate-800">{c.name_ar}</span>
                                          </div>
                                          <p className="text-xs text-slate-500 leading-relaxed">{c.description_ar}</p>
                                          {c.can_disable && (
                                            <Badge className="mt-1.5 bg-yellow-100 text-yellow-700 border border-yellow-300 text-[10px]">
                                              قابل للتعطيل
                                            </Badge>
                                          )}
                                        </div>
                                        <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-1" />
                                      </div>
                                    );
                                  })
                                )}
                              </div>
                            </>
                          );
                        })()}
                      </div>
                    </div>

                    {/* ===== النصف الثاني: القيود التفضيلية (Soft Constraints) ===== */}
                    <div className="flex flex-col">
                      <div className="bg-gradient-to-br from-amber-50 to-orange-50 border-2 border-amber-200 rounded-2xl overflow-hidden flex flex-col h-full">
                        <div className="p-4 border-b border-amber-200 bg-white/60">
                          <div className="flex items-center gap-2.5 mb-1.5">
                            <div className="w-9 h-9 rounded-xl bg-amber-500 flex items-center justify-center shadow-sm">
                              <Sliders className="h-4.5 w-4.5 text-white" />
                            </div>
                            <div className="flex-1">
                              <h3 className="text-base font-bold text-amber-800">القيود التفضيلية</h3>
                              <p className="text-[11px] text-amber-500 mt-0.5">Soft Constraints</p>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-emerald-600 font-semibold">{softConstraints.filter(c => c.is_active).length} مفعّل</span>
                              <span className="text-xs text-slate-300">|</span>
                              <span className="text-xs text-slate-400">{softConstraints.filter(c => !c.is_active).length} معطّل</span>
                            </div>
                          </div>
                          <div className="flex items-center justify-between mt-2">
                            <p className="text-xs text-amber-600/80">تؤثر على جودة الجدول — يمكن تفعيلها وضبط أولويتها</p>
                            <div className="flex gap-1.5">
                              <button
                                onClick={() => toggleAllConstraints(true)}
                                className="text-[10px] px-2 py-1 rounded-md border border-emerald-300 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 transition-all"
                              >
                                تفعيل الكل
                              </button>
                              <button
                                onClick={() => toggleAllConstraints(false)}
                                className="text-[10px] px-2 py-1 rounded-md border border-slate-300 text-slate-500 bg-white hover:bg-slate-50 transition-all"
                              >
                                تعطيل الكل
                              </button>
                            </div>
                          </div>
                        </div>

                        {(() => {
                          const softCategoryLabels = {
                            all: { label: 'الكل', color: 'amber' },
                            distribution: { label: 'توزيع الحصص', color: 'teal' },
                            teacher_comfort: { label: 'راحة المعلم', color: 'blue' },
                            pedagogy: { label: 'الجانب التربوي', color: 'purple' },
                            fairness: { label: 'العدالة', color: 'green' }
                          };
                          const softGrouped = {};
                          softConstraints.forEach(c => {
                            const cat = c.category || 'other';
                            if (!softGrouped[cat]) softGrouped[cat] = [];
                            softGrouped[cat].push(c);
                          });
                          const softCats = Object.keys(softGrouped);
                          const filteredSoft = activeSoftTab === 'all' ? softConstraints : (softGrouped[activeSoftTab] || []);

                          return (
                            <>
                              <div className="flex flex-wrap gap-1.5 p-3 border-b border-amber-100 bg-white/40">
                                {['all', ...softCats].map(cat => {
                                  const info = softCategoryLabels[cat] || { label: cat, color: 'slate' };
                                  const count = cat === 'all' ? softConstraints.length : (softGrouped[cat]?.length || 0);
                                  return (
                                    <button
                                      key={cat}
                                      onClick={() => setActiveSoftTab(cat)}
                                      className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all font-medium ${
                                        activeSoftTab === cat
                                          ? 'bg-amber-500 text-white border-amber-500 shadow-sm'
                                          : 'bg-white text-slate-600 border-slate-200 hover:border-amber-300 hover:text-amber-600'
                                      }`}
                                    >
                                      {info.label} ({count})
                                    </button>
                                  );
                                })}
                              </div>
                              <div className="flex-1 overflow-y-auto p-3 space-y-2.5" style={{ maxHeight: '520px' }}>
                                {filteredSoft.length === 0 ? (
                                  <div className="text-center py-8 text-slate-400">
                                    <Sliders className="h-10 w-10 mx-auto mb-2 opacity-40" />
                                    <p className="text-sm">{softConstraints.length === 0 ? 'لا توجد قيود تفضيلية' : 'لا توجد قيود في هذا التصنيف'}</p>
                                  </div>
                                ) : (
                                  filteredSoft.map(c => {
                                    const weightPct = c.weight * 10;
                                    const priorityLabel = c.weight >= 8 ? 'عالية' : c.weight >= 5 ? 'متوسطة' : 'منخفضة';
                                    const priorityStyles = c.weight >= 8
                                      ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
                                      : c.weight >= 5
                                        ? 'bg-amber-100 text-amber-700 border-amber-200'
                                        : 'bg-slate-100 text-slate-600 border-slate-200';
                                    return (
                                      <div
                                        key={c.code}
                                        className={`rounded-xl border-2 transition-all duration-200 overflow-hidden ${
                                          c.is_active
                                            ? 'border-amber-200 bg-white'
                                            : 'border-slate-100 bg-slate-50/60 opacity-60'
                                        }`}
                                      >
                                        <div className="flex items-center justify-between p-3 pb-1.5">
                                          <div className="flex items-center gap-2.5">
                                            <Switch
                                              checked={c.is_active}
                                              onCheckedChange={() => handleSoftConstraintToggle(c.code)}
                                            />
                                            <div>
                                              <div className="flex items-center gap-1.5">
                                                <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1 py-0.5 rounded">{c.code}</span>
                                                <span className={`text-sm font-medium ${c.is_active ? 'text-slate-800' : 'text-slate-400'}`}>
                                                  {c.name_ar}
                                                </span>
                                              </div>
                                              {c.description_ar && (
                                                <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-1">{c.description_ar}</p>
                                              )}
                                            </div>
                                          </div>
                                          {c.is_active && (
                                            <Badge className={`text-[10px] border ${priorityStyles}`}>
                                              {priorityLabel}
                                            </Badge>
                                          )}
                                        </div>
                                        {c.is_active && (
                                          <div className="px-3 pb-3 pt-1">
                                            <div className="flex items-center gap-2.5">
                                              <span className="text-[11px] text-slate-500 w-12 shrink-0">الأولوية</span>
                                              <input
                                                type="range"
                                                min="1"
                                                max="10"
                                                step="1"
                                                value={c.weight}
                                                onChange={(e) => handleSoftConstraintWeight(c.code, parseInt(e.target.value))}
                                                className="flex-1 h-1.5 rounded-full accent-amber-500 cursor-pointer"
                                              />
                                              <span className="text-xs font-bold w-8 text-start text-amber-600">
                                                {c.weight}/10
                                              </span>
                                            </div>
                                            <div className="flex gap-1.5 mt-1.5 me-12">
                                              {[{label:'منخفض', val:3},{label:'متوسط', val:6},{label:'عالي', val:9}].map(p => (
                                                <button
                                                  key={p.val}
                                                  onClick={() => handleSoftConstraintWeight(c.code, p.val)}
                                                  className={`text-[10px] px-2 py-0.5 rounded-md border transition-all ${
                                                    c.weight === p.val
                                                      ? 'bg-amber-500 text-white border-amber-500'
                                                      : 'bg-white text-slate-500 border-slate-200 hover:border-amber-300'
                                                  }`}
                                                >
                                                  {p.label}
                                                </button>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })
                                )}
                              </div>
                            </>
                          );
                        })()}

                        <div className="p-3 border-t border-amber-100 bg-white/40">
                          <p className="text-[11px] text-slate-400 text-center">
                            التغييرات تُحفظ تلقائياً — تُطبَّق على الجداول الجديدة فقط
                          </p>
                        </div>
                      </div>
                    </div>

                  </div>
                </TabsContent>
              </Tabs>
            </div>
          )}
          
          {/* ========================================= */}
          {/* ACADEMIC SECTION - الهيكل الأكاديمي */}
          {/* ========================================= */}
          {activeSection === 'academic' && (
            <div className="space-y-6">
              <AcademicStructureContent />
            </div>
          )}
          
          {/* ========================================= */}
          {/* STATIC SECTION - البيانات الثابتة */}
          {/* ========================================= */}
          {activeSection === 'static' && (
            <div className="space-y-6">
              {/* Static Tabs - one row */}
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="w-full h-auto bg-white rounded-2xl p-1.5 shadow-sm border border-slate-200 mb-6 flex flex-row gap-0.5">
                  {staticTabs.map((tab) => (
                    <TabsTrigger
                      key={tab.id}
                      value={tab.id}
                      className="flex-1 min-w-0 rounded-xl text-[10px] sm:text-xs py-2.5 px-1 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-md transition-all flex flex-col items-center gap-1 text-slate-500 hover:text-slate-700"
                      data-testid={`tab-${tab.id}`}
                    >
                      <tab.icon className="h-3.5 w-3.5 sm:h-4 sm:w-4 flex-shrink-0" />
                      <span className="truncate w-full text-center leading-tight">{tab.label}</span>
                    </TabsTrigger>
                  ))}
                </TabsList>
                
                {/* ======= TAB: المنهج الرسمي ======= */}
                <TabsContent value="curriculum" className="space-y-6">
                  <Card className="bg-white shadow-sm border-emerald-200">
                    <CardHeader className="bg-emerald-50">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-emerald-500 flex items-center justify-center">
                          <BookOpen className="h-6 w-6 text-white" />
                        </div>
                        <div>
                          <CardTitle className="text-xl text-emerald-800">المنهج الدراسي الرسمي</CardTitle>
                          <CardDescription className="text-emerald-600">بيانات وزارة التعليم السعودية</CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="p-6">
                      {officialCurriculumStats && (
                        <div className="grid grid-cols-3 md:grid-cols-6 gap-4 mb-6">
                          {[
                            { label: 'مرحلة', value: officialCurriculumStats.stages, color: 'emerald' },
                            { label: 'مسار', value: officialCurriculumStats.tracks, color: 'blue' },
                            { label: 'صف', value: officialCurriculumStats.grades, color: 'violet' },
                            { label: 'مادة', value: officialCurriculumStats.subjects, color: 'amber' },
                            { label: 'توزيع', value: officialCurriculumStats.grade_subject_mappings, color: 'rose' },
                            { label: 'رتبة معلم', value: officialCurriculumStats.teacher_rank_loads, color: 'cyan' }
                          ].map((stat, idx) => (
                            <div key={idx} className={`text-center p-4 bg-${stat.color}-50 rounded-xl border border-${stat.color}-200`}>
                              <p className={`text-2xl font-bold text-${stat.color}-700`}>{stat.value}</p>
                              <p className={`text-xs text-${stat.color}-600`}>{stat.label}</p>
                            </div>
                          ))}
                        </div>
                      )}
                      
                    </CardContent>
                  </Card>
                </TabsContent>
                
                {/* ======= TAB: المراحل والمسارات ======= */}
                <TabsContent value="stages" className="space-y-6">
                  {/* المراحل الدراسية */}
                  <Card className="bg-white shadow-sm">
                    <CardHeader>
                      <CardTitle className="text-lg flex items-center gap-2">
                        <Layers className="h-5 w-5 text-emerald-600" />
                        المراحل الدراسية ({officialStages.length})
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid md:grid-cols-3 gap-4">
                        {officialStages.map((stage) => (
                          <div key={stage.id} className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
                            <p className="font-bold text-emerald-800">{stage.name_ar}</p>
                            <p className="text-sm text-emerald-600">{stage.name_en}</p>
                            <p className="text-xs text-emerald-500 mt-2">{stage.grades_count} صفوف</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* المسارات التعليمية */}
                  <Card className="bg-white shadow-sm">
                    <CardHeader>
                      <CardTitle className="text-lg flex items-center gap-2">
                        <ChevronRight className="h-5 w-5 text-blue-600" />
                        المسارات التعليمية ({officialTracks.length})
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid md:grid-cols-4 gap-3">
                        {officialTracks.map((track) => (
                          <div key={track.id} className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                            <p className="font-medium text-blue-800 text-sm">{track.name_ar}</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
                
                {/* ======= TAB: النصاب التعليمي ======= */}
                <TabsContent value="rank-loads" className="space-y-6">
                  <Card className="bg-white shadow-sm">
                    <CardHeader>
                      <CardTitle className="text-lg flex items-center gap-2">
                        <Award className="h-5 w-5 text-violet-600" />
                        النصاب الرسمي للمعلمين حسب الرتب ({officialRankLoads.length})
                      </CardTitle>
                      <CardDescription>عدد الحصص الأسبوعية المطلوبة لكل رتبة</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid md:grid-cols-4 gap-4">
                        {officialRankLoads.map((rank) => (
                          <div key={rank.id} className="p-4 bg-violet-50 rounded-xl border border-violet-200 text-center">
                            <p className="font-bold text-violet-800">{rank.rank_name_ar}</p>
                            <p className="text-3xl font-bold text-violet-600 mt-2">{rank.weekly_periods}</p>
                            <p className="text-xs text-violet-500">حصة/أسبوع</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
                
                {/* ======= TAB: توزيع المواد ======= */}
                <TabsContent value="subject-distribution" className="space-y-6">
                  <Card className="bg-white shadow-sm border-rose-100">
                    <CardHeader className="bg-rose-50/50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 rounded-xl bg-rose-500 flex items-center justify-center">
                            <Target className="h-6 w-6 text-white" />
                          </div>
                          <div>
                            <CardTitle className="text-xl text-rose-800">توزيع المواد الرسمي</CardTitle>
                            <CardDescription className="text-rose-600">الخطة الدراسية المعتمدة من وزارة التعليم</CardDescription>
                          </div>
                        </div>
                        <Badge variant="outline" className="bg-rose-100 text-rose-700 border-rose-300">
                          <Lock className="h-3 w-3 ml-1" />
                          للقراءة فقط
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="p-0">
                      {/* Stages Accordion */}
                      <div className="divide-y divide-slate-200">
                        {officialStages.map((stage) => (
                          <div key={stage.id} className="bg-white">
                            {/* Stage Header */}
                            <button
                              onClick={() => toggleStageExpand(stage.id)}
                              className={`w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors ${
                                expandedStages[stage.id] ? 'bg-slate-50' : ''
                              }`}
                              data-testid={`stage-expand-${stage.id}`}
                            >
                              <div className="flex items-center gap-3">
                                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                                  expandedStages[stage.id] ? 'bg-emerald-500 text-white' : 'bg-emerald-100 text-emerald-600'
                                }`}>
                                  <GraduationCap className="h-5 w-5" />
                                </div>
                                <div className="text-right">
                                  <p className="font-bold text-slate-800">{stage.name_ar}</p>
                                  <p className="text-xs text-slate-500">{stage.grades_count} صفوف</p>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                {loadingCurriculum[stage.id] && (
                                  <RefreshCw className="h-4 w-4 animate-spin text-slate-400" />
                                )}
                                <ChevronRight className={`h-5 w-5 text-slate-400 transition-transform ${
                                  expandedStages[stage.id] ? 'rotate-90' : ''
                                }`} />
                              </div>
                            </button>
                            
                            {/* Stage Content - Tracks */}
                            {expandedStages[stage.id] && stageCurriculums[stage.id] && (
                              <div className="pr-6 pb-4">
                                {stageCurriculums[stage.id].tracks?.map((track) => (
                                  <div key={track.id} className="mr-4 mt-2 border-r-2 border-blue-200">
                                    {/* Track Header */}
                                    <button
                                      onClick={() => toggleTrackExpand(track.id)}
                                      className="w-full flex items-center justify-between p-3 hover:bg-blue-50 rounded-lg transition-colors mr-2"
                                      data-testid={`track-expand-${track.id}`}
                                    >
                                      <div className="flex items-center gap-2">
                                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                                          expandedTracks[track.id] ? 'bg-blue-500 text-white' : 'bg-blue-100 text-blue-600'
                                        }`}>
                                          <Layers className="h-4 w-4" />
                                        </div>
                                        <div className="text-right">
                                          <p className="font-medium text-slate-700">{track.name_ar}</p>
                                          <p className="text-xs text-slate-500">{track.grades_count} صف</p>
                                        </div>
                                      </div>
                                      <ChevronRight className={`h-4 w-4 text-slate-400 transition-transform ${
                                        expandedTracks[track.id] ? 'rotate-90' : ''
                                      }`} />
                                    </button>
                                    
                                    {/* Track Content - Grades */}
                                    {expandedTracks[track.id] && track.grades?.map((grade) => (
                                      <div key={grade.id} className="mr-8 mt-2 border-r-2 border-violet-200">
                                        {/* Grade Header */}
                                        <button
                                          onClick={() => toggleGradeExpand(grade.id)}
                                          className="w-full flex items-center justify-between p-3 hover:bg-violet-50 rounded-lg transition-colors mr-2"
                                          data-testid={`grade-expand-${grade.id}`}
                                        >
                                          <div className="flex items-center gap-2">
                                            <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                                              expandedGrades[grade.id] ? 'bg-violet-500 text-white' : 'bg-violet-100 text-violet-600'
                                            }`}>
                                              <BookOpen className="h-4 w-4" />
                                            </div>
                                            <div className="text-right">
                                              <p className="font-medium text-slate-700 text-sm">{grade.name_ar}</p>
                                              <p className="text-xs text-slate-500">
                                                {grade.subjects_count} مادة | {grade.total_annual_periods} حصة سنوياً
                                              </p>
                                            </div>
                                          </div>
                                          <ChevronRight className={`h-4 w-4 text-slate-400 transition-transform ${
                                            expandedGrades[grade.id] ? 'rotate-90' : ''
                                          }`} />
                                        </button>
                                        
                                        {/* Grade Content - Subjects Table */}
                                        {expandedGrades[grade.id] && (
                                          <div className="mr-8 mt-2 mb-4 bg-white rounded-lg border border-slate-200 overflow-hidden">
                                            <table className="w-full text-sm">
                                              <thead className="bg-slate-100">
                                                <tr>
                                                  <th className="text-right p-3 font-medium text-slate-700">#</th>
                                                  <th className="text-right p-3 font-medium text-slate-700">المادة</th>
                                                  <th className="text-center p-3 font-medium text-slate-700">الحصص السنوية</th>
                                                  <th className="text-center p-3 font-medium text-slate-700">الحصص الأسبوعية</th>
                                                  <th className="text-center p-3 font-medium text-slate-700">النوع</th>
                                                  <th className="text-center p-3 font-medium text-slate-700">الحالة</th>
                                                </tr>
                                              </thead>
                                              <tbody className="divide-y divide-slate-100">
                                                {grade.subjects?.map((subj, idx) => (
                                                  <tr key={subj.id || idx} className="hover:bg-slate-50">
                                                    <td className="p-3 text-slate-500">{idx + 1}</td>
                                                    <td className="p-3">
                                                      <p className="font-medium text-slate-800">{subj.subject_name_ar}</p>
                                                      <p className="text-xs text-slate-400">{subj.subject_name_en}</p>
                                                    </td>
                                                    <td className="p-3 text-center">
                                                      <span className="font-bold text-emerald-700">{subj.annual_periods}</span>
                                                    </td>
                                                    <td className="p-3 text-center">
                                                      <span className="font-bold text-blue-700">
                                                        {(() => {
                                                          const weekly = subj.weekly_periods ?? subj.weekly_sessions ?? (subj.annual_periods ? Math.round((subj.annual_periods / 36) * 10) / 10 : null) ?? (subj.annual_sessions ? Math.round((subj.annual_sessions / 36) * 10) / 10 : '—');
                                                          return typeof weekly === 'number' ? weekly.toFixed(1) : weekly;
                                                        })()}
                                                      </span>
                                                    </td>
                                                    <td className="p-3 text-center">
                                                      <Badge 
                                                        variant="outline" 
                                                        className={
                                                          subj.period_type === 'class_period' 
                                                            ? 'bg-green-50 text-green-700 border-green-200' 
                                                            : 'bg-amber-50 text-amber-700 border-amber-200'
                                                        }
                                                      >
                                                        {subj.period_type === 'class_period' ? 'حصة صفية' : 'فترة لاصفية'}
                                                      </Badge>
                                                    </td>
                                                    <td className="p-3 text-center">
                                                      <Badge variant="outline" className="bg-slate-100 text-slate-600 border-slate-200">
                                                        <Lock className="h-3 w-3 ml-1" />
                                                        رسمي
                                                      </Badge>
                                                    </td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                            {/* Grade Summary */}
                                            <div className="bg-slate-50 p-3 flex justify-around text-sm border-t">
                                              <div className="text-center">
                                                <p className="font-bold text-emerald-700">{grade.subjects?.length || 0}</p>
                                                <p className="text-xs text-slate-500">مادة</p>
                                              </div>
                                              <div className="text-center">
                                                <p className="font-bold text-blue-700">{grade.total_annual_periods}</p>
                                                <p className="text-xs text-slate-500">حصة سنوية</p>
                                              </div>
                                              <div className="text-center">
                                                <p className="font-bold text-violet-700">
                                                  {grade.subjects?.filter(s => s.period_type === 'class_period').length || 0}
                                                </p>
                                                <p className="text-xs text-slate-500">حصة صفية</p>
                                              </div>
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                      
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
            </div>
          )}
          </div>
        </div>
      </div>
      
      {/* ================= Modals ================= */}
      
      {/* Break/Prayer Modal */}
      {showBreakModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir="rtl">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="p-6 border-b">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Coffee className="h-5 w-5 text-[#1C3D74]" />
                {editingBreak ? 'تعديل الفترة' : 'إضافة فترة جديدة'}
              </h3>
            </div>
            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
              handleSaveBreak({
                name: formData.get('name'),
                type: formData.get('type'),
                afterPeriod: parseInt(formData.get('afterPeriod')),
                duration: parseInt(formData.get('duration'))
              });
            }} className="p-6 space-y-4">
              <div>
                <Label>اسم الفترة</Label>
                <Input name="name" defaultValue={editingBreak?.name || ''} placeholder="مثال: الاستراحة الأولى" required className="mt-1" />
              </div>
              <div>
                <Label>نوع الفترة</Label>
                <Select name="type" defaultValue={editingBreak?.type || 'break'}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="break">استراحة</SelectItem>
                    <SelectItem value="prayer">صلاة</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>بعد الحصة رقم</Label>
                  <Select name="afterPeriod" defaultValue={String(editingBreak?.afterPeriod || 2)}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1,2,3,4,5,6,7,8].map(n => (
                        <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>المدة (دقيقة)</Label>
                  <Select name="duration" defaultValue={String(editingBreak?.duration || 15)}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[5, 10, 15, 20, 25, 30].map(n => (
                        <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowBreakModal(false)}>إلغاء</Button>
                <Button type="submit" className="bg-[#1C3D74]">{editingBreak ? 'تحديث' : 'إضافة'}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      {/* Unavailability Modal */}
      {showUnavailabilityModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir="rtl">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="p-6 border-b">
              <h3 className="text-lg font-bold flex items-center gap-2">
                {unavailabilityType === 'teacher' ? <UserX className="h-5 w-5 text-amber-600" /> : <DoorClosed className="h-5 w-5 text-red-600" />}
                إضافة فترة عدم توفر {unavailabilityType === 'teacher' ? 'معلم' : 'فصل'}
              </h3>
            </div>
            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
              handleSaveUnavailability({
                [unavailabilityType === 'teacher' ? 'teacher_id' : 'class_id']: formData.get('entity_id'),
                [unavailabilityType === 'teacher' ? 'teacher_name' : 'class_name']: formData.get('entity_name'),
                day: formData.get('day'),
                period: formData.get('period')
              });
            }} className="p-6 space-y-4">
              <div>
                <Label>{unavailabilityType === 'teacher' ? 'اختر المعلم' : 'اختر الفصل'}</Label>
                <Select name="entity_id" required>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder={unavailabilityType === 'teacher' ? 'اختر معلم' : 'اختر فصل'} />
                  </SelectTrigger>
                  <SelectContent>
                    {unavailabilityType === 'teacher' 
                      ? teachers.map(t => (
                          <SelectItem key={t.id} value={t.id}>{t.full_name}</SelectItem>
                        ))
                      : classes.map(c => (
                          <SelectItem key={c.id} value={c.id}>{c.name} - {c.section}</SelectItem>
                        ))
                    }
                  </SelectContent>
                </Select>
                <input type="hidden" name="entity_name" value="" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>اليوم</Label>
                  <Select name="day" required>
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="اختر اليوم" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="الأحد">الأحد</SelectItem>
                      <SelectItem value="الإثنين">الإثنين</SelectItem>
                      <SelectItem value="الثلاثاء">الثلاثاء</SelectItem>
                      <SelectItem value="الأربعاء">الأربعاء</SelectItem>
                      <SelectItem value="الخميس">الخميس</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>الحصة</Label>
                  <Select name="period" required>
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="اختر الحصة" />
                    </SelectTrigger>
                    <SelectContent>
                      {[1,2,3,4,5,6,7].map(n => (
                        <SelectItem key={n} value={String(n)}>الحصة {n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowUnavailabilityModal(false)}>إلغاء</Button>
                <Button type="submit" className={unavailabilityType === 'teacher' ? 'bg-amber-600' : 'bg-red-600'}>إضافة</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Sidebar>
  );
}

export { SchoolSettingsPagePro };
export default SchoolSettingsPagePro;
