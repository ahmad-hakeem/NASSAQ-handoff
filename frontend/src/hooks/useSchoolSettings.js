import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { toast } from 'sonner';
import { useSensor, useSensors, PointerSensor } from '@dnd-kit/core';

export function useSchoolSettings() {
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

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    })
  );

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

  const [stageCurriculums, setStageCurriculums] = useState({});
  const [loadingCurriculum, setLoadingCurriculum] = useState({});
  const [expandedStages, setExpandedStages] = useState({});
  const [expandedTracks, setExpandedTracks] = useState({});
  const [expandedGrades, setExpandedGrades] = useState({});

  const [subjects, setSubjects] = useState([]);
  const [draggingSubject, setDraggingSubject] = useState(null);
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [assignmentSaving, setAssignmentSaving] = useState(false);
  const [assignmentSubTab, setAssignmentSubTab] = useState('subjects');
  const [classAssignments, setClassAssignments] = useState([]);
  const [classAssignmentsLoading, setClassAssignmentsLoading] = useState(false);
  const [draggingClass, setDraggingClass] = useState(null);

  const [showEditSchool, setShowEditSchool] = useState(false);
  const [showBreakModal, setShowBreakModal] = useState(false);
  const [showUnavailabilityModal, setShowUnavailabilityModal] = useState(false);
  const [editingBreak, setEditingBreak] = useState(null);
  const [unavailabilityType, setUnavailabilityType] = useState('teacher');

  const [editedSchoolInfo, setEditedSchoolInfo] = useState({});

  const [workDays, setWorkDays] = useState({
    sunday: true, monday: true, tuesday: true, wednesday: true, thursday: true,
    friday: false, saturday: false
  });

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

  const [breakTimes, setBreakTimes] = useState([
    { id: 1, name: 'الاستراحة الأولى', afterPeriod: 2, duration: 15, type: 'break' },
    { id: 2, name: 'صلاة الظهر', afterPeriod: 4, duration: 20, type: 'prayer' },
    { id: 3, name: 'الاستراحة الثانية', afterPeriod: 5, duration: 10, type: 'break' }
  ]);

  const [teacherUnavailability, setTeacherUnavailability] = useState([]);
  const [classUnavailability, setClassUnavailability] = useState([]);

  const [hardConstraints, setHardConstraints] = useState([]);
  const [softConstraints, setSoftConstraints] = useState([]);
  const [activeHardTab, setActiveHardTab] = useState('all');
  const [activeSoftTab, setActiveSoftTab] = useState('all');

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
    try {
      const schoolId = user?.tenant_id || user?.school_id || 'SCH-001';
      const res = await api.get(`/time-slots?school_id=${schoolId}`);
      setTimeSlotsCount(Array.isArray(res.data) ? res.data.length : 0);
    } catch (e) { console.error('Error fetching time slots:', e); setTimeSlotsCount(0); }
  }, [api, user]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  const saveAllSettings = async () => {
    setSaving(true);
    try {
      const dayNames = { sunday: 'الأحد', monday: 'الإثنين', tuesday: 'الثلاثاء', wednesday: 'الأربعاء', thursday: 'الخميس', friday: 'الجمعة', saturday: 'السبت' };
      const workingDays = Object.entries(workDays).filter(([_, active]) => active).map(([day]) => dayNames[day]);
      const weekendDays = Object.entries(workDays).filter(([_, active]) => !active).map(([day]) => dayNames[day]);

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
    } catch (e) { console.error('Error fetching time slots:', e); setTimeSlotsCount(0); }
  };

  const handleDragStart = (e, subject) => {
    setDraggingSubject(subject);
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('text/plain', subject.id);
  };

  const handleDragEnd = () => {
    setDraggingSubject(null);
  };

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
    } catch (e) {
      console.error('Error toggling soft constraint:', e);
      setSoftConstraints(prev => prev.map(x => x.code === code ? { ...x, is_active: !newActive } : x));
      nassaqError('حدث خطأ في تحديث القيد');
    }
  };

  const handleSoftConstraintWeight = async (code, weight) => {
    const prev = softConstraints.find(x => x.code === code)?.weight;
    setSoftConstraints(p => p.map(x => x.code === code ? { ...x, weight } : x));
    try {
      await api.put(`/school/settings/soft-constraints/${code}`, { weight });
    } catch (e) {
      console.error('Error updating constraint weight:', e);
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
    } catch (e) {
      console.error('Error toggling all constraints:', e);
      nassaqError('حدث خطأ في تحديث القيود');
      fetchData();
    }
  };

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
      setBreakTimes(prev => prev.map(b => b.id === editingBreak.id ? { ...b, ...breakData } : b));
    } else {
      const newBreak = { id: Date.now(), ...breakData };
      setBreakTimes(prev => [...prev, newBreak]);
    }
    setShowBreakModal(false);
    setHasChanges(true);
    toast.success(editingBreak ? 'تم تحديث الفترة بنجاح' : 'تم إضافة الفترة بنجاح');
  };

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

  const loadClassAssignments = async () => {
    setClassAssignmentsLoading(true);
    try {
      const res = await api.get('/teacher-class-assignments?page_size=1000');
      setClassAssignments(res.data?.data || res.data || []);
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

  useEffect(() => {
    if (assignmentSubTab === 'classes' && classAssignments.length === 0) {
      loadClassAssignments();
    }
  }, [assignmentSubTab]);

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
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return {
    navigate, api, user, nassaqWarning, nassaqConfirm, nassaqError,
    activeSection, setActiveSection, activeTab, setActiveTab,
    loading, saving, hasChanges, setHasChanges, sensors,
    schoolInfo, settings, teachers, classes, assignments, constraints,
    readinessData, officialCurriculumStats, officialStages, officialTracks, officialRankLoads,
    stageCurriculums, loadingCurriculum, expandedStages, expandedTracks, expandedGrades,
    subjects, draggingSubject, setDraggingSubject, selectedSubject, setSelectedSubject,
    assignmentSaving, assignmentSubTab, setAssignmentSubTab,
    classAssignments, classAssignmentsLoading, draggingClass, setDraggingClass,
    showEditSchool, setShowEditSchool, showBreakModal, setShowBreakModal,
    showUnavailabilityModal, setShowUnavailabilityModal,
    editingBreak, setEditingBreak, unavailabilityType, setUnavailabilityType,
    editedSchoolInfo, setEditedSchoolInfo,
    workDays, timingSettings, timeSlotsCount, generatingSlots,
    breakTimes, teacherUnavailability, classUnavailability,
    hardConstraints, softConstraints, activeHardTab, setActiveHardTab, activeSoftTab, setActiveSoftTab,
    fetchData, saveAllSettings, saveSchoolInfo, generateTimeSlots, fetchTimeSlotsCount,
    handleDragStart, handleDragEnd, handleSelectSubject, handleAssignToTeacher,
    removeAssignment, getTeacherAssignments, getSubjectById, deleteClass,
    handleSettingChange, handleWorkDayChange,
    handleSoftConstraintToggle, handleSoftConstraintWeight, toggleAllConstraints,
    handleAddBreak, handleEditBreak, handleDeleteBreak, handleSaveBreak,
    handleAddUnavailability, handleSaveUnavailability, handleDeleteUnavailability,
    loadClassAssignments, handleCreateClassAssignment, handleDeleteClassAssignment,
    toggleStageExpand, toggleTrackExpand, toggleGradeExpand,
    navigateToFix, setAssignments,
  };
}
