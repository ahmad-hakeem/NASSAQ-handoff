import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { toast } from 'sonner';
import { useSensor, useSensors, PointerSensor } from '@dnd-kit/core';
import { getApiErrorMessage } from '../utils/apiError';

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

  const validDynamicTabs = ['school-info', 'timings', 'classes', 'subjects', 'teacher-assignments', 'unavailability', 'constraints'];
  const rawTab = searchParams.get('tab') || 'school-info';
  const initialTab = validDynamicTabs.includes(rawTab) ? rawTab : 'school-info';
  const [activeTab, setActiveTab] = useState(initialTab);

  // تنبيه داخل الصفحة (Inline alert) — بديل عن الـ toast العائم في
  // تدفّقات الحفظ التي يجب أن يقرأها المسؤول قبل المتابعة (مثل تنبيه
  // النقل الذي لم يُرسَل لأي معلم بسبب حسابات غير مرتبطة).
  const [inlineAlert, setInlineAlert] = useState({ show: false, type: 'success', message: '' });
  const dismissInlineAlert = useCallback(() => {
    setInlineAlert(prev => ({ ...prev, show: false }));
  }, []);

  // مودال للحركات الحسّاسة (نجاح/تحذير/خطأ) — يوقف الشاشة ليُقرّ
  // المسؤول صراحةً قبل المتابعة، بدل بانر سريع قد يُفوَّت.
  const [successModal, setSuccessModal] = useState({ show: false, type: 'success', title: '', message: '' });
  const dismissSuccessModal = useCallback(() => {
    setSuccessModal(prev => ({ ...prev, show: false }));
  }, []);

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
  // علامة "تم التحميل مرة على الأقل" لمنع وميض "0 إسناد" قبل أوّل جلب.
  // الـ loading وحده لا يكفي لأنه يبدأ false ولا يصبح true إلا بعد تشغيل
  // الـ effect المسؤول، فبين الرسم الأوّل وتشغيل الـ effect سيظهر "0".
  const [classAssignmentsLoaded, setClassAssignmentsLoaded] = useState(false);
  // نتمييز فشل الشبكة عن "صفر فعلي" حتى لا يظهر "0 إسناد" بعد فشل الجلب.
  const [classAssignmentsError, setClassAssignmentsError] = useState(false);
  const [draggingClass, setDraggingClass] = useState(null);
  // طلب اختيار مادة: يُفتح عندما يتعذّر على الخادم اختيار مادة تلقائيًا
  // لزوج (معلم، فصل) — يعرض المواد المرشّحة ليختار المدير بدل رسالة خطأ
  // مسدودة. القيمة: { teacherId, classId, teacherName, className, message, candidates }
  const [subjectPickerRequest, setSubjectPickerRequest] = useState(null);
  const [subjectPickerSaving, setSubjectPickerSaving] = useState(false);

  const [showEditSchool, setShowEditSchool] = useState(false);
  const [showBreakModal, setShowBreakModal] = useState(false);
  const [showUnavailabilityModal, setShowUnavailabilityModal] = useState(false);
  const [editingBreak, setEditingBreak] = useState(null);
  const [unavailabilityType, setUnavailabilityType] = useState('teacher');
  const [showNoorImportModal, setShowNoorImportModal] = useState(false);
  const [noorImportType, setNoorImportType] = useState('noor_classes');

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
    breakAfterPeriod: 3,
    attendancePattern: 'winter',
    maxStandbyPerWeek: 5,
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

  const [customSoftConstraints, setCustomSoftConstraints] = useState([]);
  const [constraintPatterns, setConstraintPatterns] = useState({ builtin: [], custom: [] });
  const [otherDuties, setOtherDuties] = useState([]);
  const [workloadSummary, setWorkloadSummary] = useState([]);
  const [workloadLoading, setWorkloadLoading] = useState(false);
  const [showAddConstraintModal, setShowAddConstraintModal] = useState(false);
  const [showAddDutyModal, setShowAddDutyModal] = useState(false);

  const fetchData = useCallback(async () => {
    if (!api) return;
    setLoading(true);

    try {
      // Readiness check is the slowest endpoint (~1.5–2s uncached, ~15 sequential
      // DB queries on a shared session). It is informational and not required for
      // the page to render, so we fire it off in the background instead of
      // blocking the initial render on it.
      api
        .get('/timetable-readiness/check')
        .then((r) => setReadinessData(r.data))
        .catch(() => setReadinessData(null));

      const [
        settingsRes, teachersRes, classesRes, assignmentsRes,
        constraintsRes, schoolRes,
        subjectsRes, hardConstraintsRes, softConstraintsRes
      ] = await Promise.all([
        api.get('/school/settings').catch(() => ({ data: {} })),
        api.get('/teachers').catch(() => ({ data: [] })),
        api.get('/classes').catch(() => ({ data: [] })),
        api.get('/teacher-assignments').catch(() => ({ data: [] })),
        api.get('/school/constraints').catch(() => ({ data: [] })),
        api.get('/school/info').catch(() => ({ data: {} })),
        api.get('/school/subjects/unique').catch(() => ({ data: [] })),
        api.get('/school/settings/hard-constraints').catch(() => ({ data: { hard_constraints: [] } })),
        api.get('/school/settings/soft-constraints').catch(() => ({ data: { soft_constraints: [] } }))
      ]);

      setSettings(settingsRes.data || {});
      setTeachers(Array.isArray(teachersRes.data) ? teachersRes.data : []);
      setClasses(Array.isArray(classesRes.data) ? classesRes.data : []);
      setAssignments(Array.isArray(assignmentsRes.data) ? assignmentsRes.data : []);
      setConstraints(Array.isArray(constraintsRes.data) ? constraintsRes.data : []);
      setSchoolInfo(schoolRes.data || {});
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
        breakAfterPeriod: s.breakAfterPeriod || 3,
        attendancePattern: s.attendancePattern || s.attendance_pattern || 'winter',
        maxStandbyPerWeek: (() => {
          const n = parseInt(s.maxStandbyPerWeek, 10);
          if (!Number.isFinite(n)) return 5;
          return Math.max(1, Math.min(20, n));
        })(),
      });

      if (Array.isArray(s.breaks) && s.breaks.length > 0) {
        setBreakTimes(s.breaks.map((b, idx) => ({
          id: b.id || idx + 1,
          name: b.name || 'استراحة',
          afterPeriod: b.afterPeriod || b.after_period || idx + 2,
          duration: b.duration || 15,
          type: b.type || 'break',
          customType: b.customType || b.custom_type || '',
          day: b.day || 'all',
        })));
      }

    } catch (error) {
      console.error('Error fetching data:', error);
      nassaqError('حدث خطأ في تحميل البيانات');
    } finally {
      setLoading(false);
    }
    try {
      const schoolId = user?.tenant_id || user?.school_id;
      if (schoolId) {
        const res = await api.get(`/time-slots?school_id=${schoolId}`);
        setTimeSlotsCount(Array.isArray(res.data) ? res.data.length : 0);
      }
    } catch (e) { console.error('Error fetching time slots:', e); setTimeSlotsCount(0); }

    try {
      const [teacherUnavailRes, classUnavailRes] = await Promise.all([
        api.get('/school/settings/unavailability?entity_type=teacher').catch(() => ({ data: { items: [] } })),
        api.get('/school/settings/unavailability?entity_type=class').catch(() => ({ data: { items: [] } })),
      ]);
      setTeacherUnavailability(teacherUnavailRes.data?.items || []);
      setClassUnavailability(classUnavailRes.data?.items || []);
    } catch (e) { console.error('Error fetching unavailability:', e); }

    try {
      const [customConstraintsRes, patternsRes, dutiesRes] = await Promise.all([
        api.get('/school/settings/custom-soft-constraints').catch(() => ({ data: { constraints: [] } })),
        api.get('/school/settings/constraint-patterns').catch(() => ({ data: { builtin_patterns: [], custom_patterns: [] } })),
        api.get('/school/settings/other-duties').catch(() => ({ data: { duties: [] } })),
      ]);
      setCustomSoftConstraints(customConstraintsRes.data?.constraints || []);
      setConstraintPatterns({
        builtin: patternsRes.data?.builtin_patterns || [],
        custom: patternsRes.data?.custom_patterns || [],
      });
      setOtherDuties(dutiesRes.data?.duties || []);
    } catch (e) { console.error('Error fetching constraints/duties:', e); }
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
        principal_mobile: schoolInfo.principal_mobile || '',
        educational_pathway: schoolInfo.educational_pathway || '',
      });
    }
  }, [schoolInfo]);

  const toggleStageExpand = (stageId) => {
    setExpandedStages(prev => ({ ...prev, [stageId]: !prev[stageId] }));
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
        attendancePattern: timingSettings.attendancePattern,
        maxStandbyPerWeek: timingSettings.maxStandbyPerWeek,
        breaks: breakTimes.map(b => ({
          id: b.id,
          name: b.name,
          afterPeriod: b.afterPeriod,
          duration: b.duration,
          type: b.type,
          customType: b.customType,
          day: b.day,
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
      api.get('/timetable-readiness/check').then(r => setReadinessData(r.data)).catch(err => { if (process.env.NODE_ENV === 'development') console.warn('Timetable readiness check failed:', err.message); });
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
      const schoolId = user?.tenant_id || user?.school_id;
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
      const schoolId = user?.tenant_id || user?.school_id;
      if (!schoolId) return;
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
      const schoolId = user?.tenant_id || user?.school_id;
      const response = await api.post('/teacher-assignments', {
        teacher_id: teacher.id,
        subject_id: subjectToAssign.id,
        school_id: schoolId
      });
      // الخادم يعيد { message, assignment: { id, ... } } — قراءة response.data.id
      // وحدها كانت تُبقي المعرّف المؤقّت، فيفشل الحذف لاحقًا (DELETE على temp-…)
      // ويختفي الإسناد من الواجهة دون حذفه فعليًا.
      const realId = response.data?.assignment?.id || response.data?.id || response.data?.assignment_id || tempId;
      setAssignments(prev => prev.map(a => a.id === tempId ? { ...a, id: realId, _optimistic: false } : a));
      toast.success(`✓ إسناد "${subjectToAssign.name_ar}" إلى "${teacher.full_name || teacher.name}"`);
    } catch (error) {
      setAssignments(prev => prev.filter(a => a.id !== tempId));
      let errorMessage = 'حدث خطأ في إسناد المادة';
      if (getApiErrorMessage(error) && typeof getApiErrorMessage(error) === 'string') {
        errorMessage = getApiErrorMessage(error);
      }
      nassaqError(errorMessage);
    }
  };

  const removeAssignment = async (assignmentId) => {
    nassaqConfirm('هل أنت متأكد من إلغاء هذا الإسناد؟', async () => {
      const removed = assignments.find(a => a.id === assignmentId);
      if (!removed) return;
      const siblings = assignments.filter(
        a => a.teacher_id === removed.teacher_id && a.subject_id === removed.subject_id
      );
      const siblingIds = new Set(siblings.map(a => a.id));
      setAssignments(prev => prev.filter(a => !siblingIds.has(a.id)));
      try {
        await Promise.all(
          siblings.map(a => api.delete(`/teacher-assignments/${a.id}`).catch(() => null))
        );
        toast.success('تم إلغاء الإسناد');
      } catch (error) {
        setAssignments(prev => [...prev, ...siblings]);
        nassaqError('حدث خطأ في إلغاء الإسناد');
      }
    });
  };

  const getTeacherAssignments = (teacherId) => {
    const all = assignments.filter(a => a.teacher_id === teacherId);
    const seen = new Set();
    const deduped = [];
    for (const a of all) {
      const key = a.subject_id;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      deduped.push(a);
    }
    return deduped;
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
        if (getApiErrorMessage(error)) {
          if (typeof getApiErrorMessage(error) === 'string') {
            errorMessage = getApiErrorMessage(error);
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

  const handleSoftConstraintTargetSubjects = async (code, subjectIds) => {
    const prev_constraint = softConstraints.find(x => x.code === code);
    const prevSubjectIds = prev_constraint?.target_subject_ids || [];
    setSoftConstraints(prev => prev.map(x => x.code === code ? { ...x, target_subject_ids: subjectIds } : x));
    try {
      await api.put(`/school/settings/soft-constraints/${code}`, { target_subject_ids: subjectIds });
    } catch (e) {
      setSoftConstraints(prev => prev.map(x => x.code === code ? { ...x, target_subject_ids: prevSubjectIds } : x));
      nassaqError('حدث خطأ في تحديث المواد المستهدفة');
    }
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

  const handleHardConstraintToggle = (code) => {
    const c = hardConstraints.find(x => x.code === code);
    if (!c) return;
    // Mandatory blockers cannot be disabled — surface a branded warning
    // instead of attempting a request the backend would reject.
    if (!c.can_disable) {
      nassaqWarning('هذا القيد إلزامي ولا يمكن تعطيله');
      return;
    }
    const newActive = !c.is_active;
    const apply = async () => {
      setHardConstraints(prev => prev.map(x => x.code === code ? { ...x, is_active: newActive } : x));
      try {
        await api.put(`/school/settings/hard-constraints/${code}`, { is_active: newActive });
        // Re-read from the API so the merged (system + override) state is the
        // single source of truth rather than trusting the optimistic update.
        const res = await api.get('/school/settings/hard-constraints');
        const hc = res.data?.hard_constraints || [];
        setHardConstraints(Array.isArray(hc) ? hc : []);
        toast.success('تم تحديث القيد بنجاح');
      } catch (e) {
        setHardConstraints(prev => prev.map(x => x.code === code ? { ...x, is_active: !newActive } : x));
        nassaqError(getApiErrorMessage(e) || 'حدث خطأ في تحديث القيد');
      }
    };
    if (newActive) {
      apply();
    } else {
      nassaqConfirm(
        'سيؤدي تعطيل هذا القيد إلى استبعاده من توليد الجدول لهذه المدرسة. هل أنت متأكد؟',
        apply,
        { title: 'تأكيد تعطيل القيد', confirmText: 'نعم، عطّل', cancelText: 'إلغاء' }
      );
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

  const handleSaveUnavailability = async (data) => {
    const localId = Date.now();
    const item = { id: localId, ...data };

    if (unavailabilityType === 'teacher') {
      setTeacherUnavailability(prev => [...prev, item]);
    } else {
      setClassUnavailability(prev => [...prev, item]);
    }
    setShowUnavailabilityModal(false);
    setHasChanges(true);

    try {
      const entityId = data.teacher_id || data.class_id;
      const entityName = data.teacher_name || data.class_name;
      const res = await api.post('/school/settings/unavailability', {
        entity_type: unavailabilityType,
        entity_id: entityId,
        entity_name: entityName,
        unavailability_type: data.unavailability_type || 'recurring',
        day: data.day || null,
        period: data.period || null,
        start_date: data.start_date || null,
        end_date: data.end_date || null,
        reason: data.reason || null,
        // Class-only: where to send the students while the room is unavailable.
        // The backend ignores this for teacher records and uses it both to
        // craft a clearer notification and to flag the cell on the master grid.
        alternative_location: unavailabilityType === 'class' ? (data.alternative_location || null) : null,
      });

      const serverId = res.data?.id || localId;
      if (unavailabilityType === 'teacher') {
        setTeacherUnavailability(prev => prev.map(u => u.id === localId ? { ...u, id: serverId } : u));
      } else {
        setClassUnavailability(prev => prev.map(u => u.id === localId ? { ...u, id: serverId } : u));
      }

      const notifCount = res.data?.notifications_sent || 0;
      if (notifCount > 0) {
        // حركة حسّاسة: أُرسلت إشعارات فعلية للمعلمين — نوقف الشاشة
        // بمودال نجاح يُقرّه المسؤول صراحةً بدل بانر سريع.
        setSuccessModal({
          show: true,
          type: 'success',
          title: 'تمت الإضافة بنجاح',
          message: unavailabilityType === 'class'
            ? `تم إضافة فترة عدم التوفر وإرسال ${notifCount} إشعار للمعلمين المرتبطين بهذا الفصل.`
            : `تم إضافة فترة عدم التوفر وإرسال ${notifCount} إشعار للمعلمين.`,
        });
      } else if (
        unavailabilityType === 'class' &&
        data.alternative_location &&
        data.alternative_location.trim()
      ) {
        // الحفظ نجح لكن لم يصل أي إشعار للمعلمين — غالباً لأن سجلات
        // المعلمين المتأثرين غير مرتبطة بحسابات مستخدمين فعّالة. ننبّه
        // المسؤول صراحةً ليتحقق من حسابات المعلمين بدلاً من إخفاء الأمر.
        setSuccessModal({
          show: true,
          type: 'warning',
          title: 'تم الحفظ — لكن لم يصل أي إشعار',
          message: 'تم حفظ النقل، لكن لم يتم إخطار أي معلم — تحقّق من حسابات المعلمين المرتبطين بهذا الفصل.',
        });
      } else {
        setSuccessModal({
          show: true,
          type: 'success',
          title: 'تمت الإضافة بنجاح',
          message: 'تم إضافة فترة عدم التوفر بنجاح.',
        });
      }
    } catch (err) {
      console.error('Error saving unavailability:', err);
      if (unavailabilityType === 'teacher') {
        setTeacherUnavailability(prev => prev.filter(u => u.id !== localId));
      } else {
        setClassUnavailability(prev => prev.filter(u => u.id !== localId));
      }
      setSuccessModal({
        show: true,
        type: 'error',
        title: 'تعذّر الحفظ',
        message: 'حدث خطأ أثناء حفظ فترة عدم التوفر.',
      });
    }
  };

  const handleOpenNoorImport = (type) => {
    setNoorImportType(type);
    setShowNoorImportModal(true);
  };

  const handleDeleteUnavailability = (id, type) => {
    nassaqConfirm('هل أنت متأكد من حذف هذه الفترة؟', async () => {
      if (type === 'teacher') {
        setTeacherUnavailability(prev => prev.filter(u => u.id !== id));
      } else {
        setClassUnavailability(prev => prev.filter(u => u.id !== id));
      }
      setHasChanges(true);
      toast.success('تم حذف الفترة بنجاح');
      try {
        await api.delete(`/school/settings/unavailability/${id}`);
      } catch (err) {
        console.error('Error deleting unavailability:', err);
      }
    }, { title: 'تأكيد الحذف', confirmText: 'نعم، احذف', cancelText: 'إلغاء' });
  };

  const loadClassAssignments = async () => {
    setClassAssignmentsLoading(true);
    setClassAssignmentsError(false);
    try {
      const res = await api.get('/teacher-class-assignments?page_size=20000');
      setClassAssignments(res.data?.data || res.data || []);
      setClassAssignmentsLoaded(true);
    } catch (error) {
      console.error('Error loading class assignments:', error);
      setClassAssignmentsError(true);
    } finally {
      setClassAssignmentsLoading(false);
    }
  };

  const handleCreateClassAssignment = async (teacherId, classId, subjectId = null) => {
    try {
      await api.post('/teacher-class-assignments', {
        teacher_id: teacherId,
        class_id: classId,
        ...(subjectId ? { subject_id: subjectId } : {}),
      });
      // Re-read the canonical set instead of trusting an optimistic append —
      // the backend auto-resolves the subject and may dedupe the pairing.
      await loadClassAssignments();
      toast.success('تم إسناد الفصل للمعلم بنجاح');
      return true;
    } catch (error) {
      // Class-only assignment couldn't auto-resolve a subject for this pairing
      // (no curriculum + several candidate subjects, or none derivable from the
      // teacher record). Offer the candidates so the principal picks one here
      // instead of being bounced to another tab.
      const detail = error?.response?.data?.detail;
      if (error?.response?.status === 409 && detail?.code === 'subject_required') {
        const candidates = Array.isArray(detail.candidates) ? detail.candidates : [];
        if (candidates.length > 0 && !subjectId) {
          setSubjectPickerRequest({
            teacherId,
            classId,
            teacherName: detail.teacher_name || '',
            className: detail.class_name || '',
            message: detail.message || '',
            candidates,
          });
          return false;
        }
        nassaqError(detail.message || 'يرجى إسناد مادة مناسبة للمعلم أولًا.');
        return false;
      }
      nassaqError(getApiErrorMessage(error) || 'فشل في إنشاء الإسناد');
      return false;
    }
  };

  const cancelSubjectPicker = () => setSubjectPickerRequest(null);

  const confirmSubjectPicker = async (subjectId) => {
    if (!subjectPickerRequest || !subjectId) return;
    setSubjectPickerSaving(true);
    try {
      const ok = await handleCreateClassAssignment(
        subjectPickerRequest.teacherId, subjectPickerRequest.classId, subjectId,
      );
      if (ok) setSubjectPickerRequest(null);
    } finally {
      setSubjectPickerSaving(false);
    }
  };

  const handleDeleteClassAssignment = async (assignmentId) => {
    try {
      await api.delete(`/teacher-class-assignments/${assignmentId}`);
      // Re-read the canonical set so the list reflects the unassignment
      // (and any kept-but-flagged lessons) rather than an optimistic guess.
      await loadClassAssignments();
      toast.success('تم حذف الإسناد بنجاح');
    } catch (error) {
      // If the assignment already doesn't exist on the server, resync silently.
      if (error?.response?.status === 404) {
        await loadClassAssignments();
        toast.success('تم حذف الإسناد بنجاح');
        return;
      }
      nassaqError('فشل في حذف الإسناد');
    }
  };

  useEffect(() => {
    if (assignmentSubTab === 'classes' && classAssignments.length === 0 && !classAssignmentsLoading) {
      loadClassAssignments();
    }
  }, [assignmentSubTab]);

  // تحميل عدّاد إسناد الفصول فور دخول تبويب "إسناد المعلمين"، حتى لا
  // يظهر بادج "0 إسناد" خادع بجوار التبويب الفرعي قبل أن يفتحه المدير.
  // الـ guard على length يمنع إعادة الجلب لو سبق تحميله (مثلاً المستخدم
  // فتح تبويب الفصول الفرعي ثم رجع لتبويب الفصول).
  useEffect(() => {
    if (activeTab === 'teacher-assignments' && classAssignments.length === 0 && !classAssignmentsLoading) {
      loadClassAssignments();
    }
  }, [activeTab]);

  const handleAddCustomConstraint = async (constraintData) => {
    try {
      const res = await api.post('/school/settings/custom-soft-constraints', constraintData);
      const newConstraint = res.data?.constraint;
      if (newConstraint) {
        setCustomSoftConstraints(prev => [...prev, newConstraint]);
        toast.success('تم إضافة القيد التفضيلي بنجاح');
      }
      setShowAddConstraintModal(false);
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || 'حدث خطأ في إضافة القيد');
    }
  };

  const handleUpdateCustomConstraint = async (constraintId, updates) => {
    try {
      const res = await api.put(`/school/settings/custom-soft-constraints/${constraintId}`, updates);
      const updated = res.data?.constraint;
      if (updated) {
        setCustomSoftConstraints(prev => prev.map(c => c.id === constraintId ? updated : c));
      } else {
        setCustomSoftConstraints(prev => prev.map(c => c.id === constraintId ? { ...c, ...updates } : c));
      }
      toast.success('تم تحديث القيد بنجاح');
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || 'حدث خطأ في تحديث القيد');
    }
  };

  const handleDeleteCustomConstraint = (constraintId) => {
    nassaqConfirm('هل أنت متأكد من حذف هذا القيد؟', async () => {
      try {
        await api.delete(`/school/settings/custom-soft-constraints/${constraintId}`);
        setCustomSoftConstraints(prev => prev.filter(c => c.id !== constraintId));
        toast.success('تم حذف القيد بنجاح');
      } catch (e) {
        nassaqError('حدث خطأ في حذف القيد');
      }
    });
  };

  const handleToggleCustomConstraint = async (constraintId) => {
    const c = customSoftConstraints.find(x => x.id === constraintId);
    if (!c) return;
    const newActive = !c.is_active;
    setCustomSoftConstraints(prev => prev.map(x => x.id === constraintId ? { ...x, is_active: newActive } : x));
    try {
      await api.put(`/school/settings/custom-soft-constraints/${constraintId}`, { is_active: newActive });
    } catch (e) {
      setCustomSoftConstraints(prev => prev.map(x => x.id === constraintId ? { ...x, is_active: !newActive } : x));
      nassaqError('حدث خطأ في تحديث القيد');
    }
  };

  const handleAddConstraintPattern = async (patternData) => {
    try {
      const res = await api.post('/school/settings/constraint-patterns', patternData);
      const newPattern = res.data?.pattern;
      if (newPattern) {
        setConstraintPatterns(prev => ({ ...prev, custom: [...(prev.custom || []), newPattern] }));
        toast.success('تم إضافة النمط بنجاح');
      }
      return newPattern;
    } catch (e) {
      nassaqError('حدث خطأ في إضافة النمط');
      return null;
    }
  };

  const handleUpdateConstraintPattern = async (patternId, patternData) => {
    try {
      const res = await api.put(`/school/settings/constraint-patterns/${patternId}`, patternData);
      const updated = res.data?.pattern;
      if (updated) {
        setConstraintPatterns(prev => ({
          ...prev,
          custom: (prev.custom || []).map(p => p.id === patternId ? updated : p),
        }));
        toast.success('تم تحديث النمط بنجاح');
      }
      return updated;
    } catch (e) {
      nassaqError('حدث خطأ في تحديث النمط');
      return null;
    }
  };

  const handleDeleteConstraintPattern = (patternId) => {
    nassaqConfirm('هل أنت متأكد من حذف هذا النمط؟', async () => {
      try {
        await api.delete(`/school/settings/constraint-patterns/${patternId}`);
        setConstraintPatterns(prev => ({
          ...prev,
          custom: (prev.custom || []).filter(p => p.id !== patternId),
        }));
        toast.success('تم حذف النمط بنجاح');
      } catch (e) {
        nassaqError('حدث خطأ في حذف النمط');
      }
    });
  };

  const handleAddOtherDuty = async (dutyData) => {
    try {
      const res = await api.post('/school/settings/other-duties', dutyData);
      const newDuty = res.data?.duty;
      if (newDuty) {
        setOtherDuties(prev => [...prev, newDuty]);
        toast.success('تم إضافة التكليف بنجاح');
      }
      setShowAddDutyModal(false);
      fetchWorkloadSummary();
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || 'حدث خطأ في إضافة التكليف');
    }
  };

  const handleUpdateOtherDuty = async (dutyId, updates) => {
    try {
      const res = await api.put(`/school/settings/other-duties/${dutyId}`, updates);
      const updated = res.data?.duty;
      if (updated) {
        setOtherDuties(prev => prev.map(d => d.id === dutyId ? updated : d));
      } else {
        setOtherDuties(prev => prev.map(d => d.id === dutyId ? { ...d, ...updates } : d));
      }
      toast.success('تم تحديث التكليف بنجاح');
      fetchWorkloadSummary();
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || 'حدث خطأ في تحديث التكليف');
    }
  };

  const handleDeleteOtherDuty = (dutyId) => {
    nassaqConfirm('هل أنت متأكد من حذف هذا التكليف؟', async () => {
      try {
        await api.delete(`/school/settings/other-duties/${dutyId}`);
        setOtherDuties(prev => prev.filter(d => d.id !== dutyId));
        toast.success('تم حذف التكليف بنجاح');
        fetchWorkloadSummary();
      } catch (e) {
        nassaqError('حدث خطأ في حذف التكليف');
      }
    });
  };

  const fetchWorkloadSummary = useCallback(async () => {
    if (!api) return;
    setWorkloadLoading(true);
    try {
      const res = await api.get('/school/settings/workload-summary');
      setWorkloadSummary(res.data?.summary || []);
    } catch (e) {
      console.error('Error fetching workload summary:', e);
    } finally {
      setWorkloadLoading(false);
    }
  }, [api]);

  const handleWorkloadOverride = async (teacherId, standbyOverride) => {
    const prevWorkloadSummary = workloadSummary;
    try {
      setWorkloadSummary(prev => prev.map(w => {
        if (w.teacher_id !== teacherId) return w;
        const computedStandby = standbyOverride === null
          ? Math.max(0, (w.total_periods - w.used_periods))
          : standbyOverride;
        return { ...w, standby_periods: computedStandby, manual_override: standbyOverride !== null };
      }));
      await api.put(`/school/settings/workload-override/${teacherId}`, { standby_override: standbyOverride });
      toast.success('تم تحديث حصص الانتظار');
    } catch (e) {
      setWorkloadSummary(prevWorkloadSummary);
      nassaqError('حدث خطأ في تحديث حصص الانتظار');
    }
  };

  const navigateToFix = (category) => {
    // بعد المهمة #114 انتقلت تبويبات إعدادات الجدول الخمس إلى صفحة
    // "الجدول المدرسي الذكي" تحت تبويب "إعدادات الجدول المدرسي"
    // (`/school/schedule?tab=settings&sub=...`). أما الفئات المتعلقة
    // بالهيكل الأكاديمي فتبقى داخل صفحة إعدادات المدرسة، والفئات غير
    // المعروفة تُعيد المستخدم إلى لوحة الإعدادات بدون اختيار تبويب
    // فرعي حتى لا نوجِّهه عشوائياً إلى مكان غير ملائم.
    const scheduleSubTabByCategory = {
      // أسماء فئات الإصدار السابق (لم تَعُد ترسلها واجهة الجاهزية لكن
      // قد تأتي من روابط محفوظة).
      academic_context: 'timings',
      school_days: 'timings',
      day_structure: 'timings',
      classes: 'classes',
      teachers: 'teacher-assignments',
      teacher_assignments: 'teacher-assignments',
      // أسماء الفئات الحالية القادمة من /api/timetable-readiness/check.
      time_structure: 'timings',
      teaching_staff: 'teacher-assignments',
      teaching_relationships: 'teacher-assignments',
      constraints: 'constraints',
      generation_ready: 'teacher-assignments',
    };
    const academicSectionCategories = new Set([
      'academic_structure',
      'academic_entities',
    ]);

    const sub = scheduleSubTabByCategory[category];
    if (sub) {
      navigate(`/principal/schedule?tab=settings&sub=${sub}`);
    } else if (academicSectionCategories.has(category)) {
      navigate('/principal/settings?section=academic');
    } else {
      // فئة غير معروفة — نرجع المستخدم إلى صفحة الإعدادات العامة دون
      // اختيار تبويب فرعي حتى لا نُحوِّله إلى تبويب لا علاقة له بالمشكلة.
      navigate('/principal/settings');
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return {
    navigate, api, user, nassaqWarning, nassaqConfirm, nassaqError,
    activeSection, setActiveSection, activeTab, setActiveTab,
    inlineAlert, setInlineAlert, dismissInlineAlert,
    successModal, setSuccessModal, dismissSuccessModal,
    loading, saving, hasChanges, setHasChanges, sensors,
    schoolInfo, settings, teachers, classes, assignments, constraints,
    readinessData,
    stageCurriculums, loadingCurriculum, expandedStages, expandedTracks, expandedGrades,
    subjects, draggingSubject, setDraggingSubject, selectedSubject, setSelectedSubject,
    assignmentSaving, assignmentSubTab, setAssignmentSubTab,
    classAssignments, classAssignmentsLoading, classAssignmentsLoaded, classAssignmentsError, draggingClass, setDraggingClass,
    showEditSchool, setShowEditSchool, showBreakModal, setShowBreakModal,
    showUnavailabilityModal, setShowUnavailabilityModal,
    editingBreak, setEditingBreak, unavailabilityType, setUnavailabilityType,
    showNoorImportModal, setShowNoorImportModal, noorImportType, setNoorImportType,
    editedSchoolInfo, setEditedSchoolInfo,
    workDays, timingSettings, timeSlotsCount, generatingSlots,
    breakTimes, teacherUnavailability, classUnavailability,
    hardConstraints, softConstraints, activeHardTab, setActiveHardTab, activeSoftTab, setActiveSoftTab,
    customSoftConstraints, setCustomSoftConstraints,
    constraintPatterns, setConstraintPatterns,
    otherDuties, setOtherDuties,
    workloadSummary, workloadLoading,
    showAddConstraintModal, setShowAddConstraintModal,
    showAddDutyModal, setShowAddDutyModal,
    fetchData, saveAllSettings, saveSchoolInfo, generateTimeSlots, fetchTimeSlotsCount,
    handleDragStart, handleDragEnd, handleSelectSubject, handleAssignToTeacher,
    removeAssignment, getTeacherAssignments, getSubjectById, deleteClass,
    handleSettingChange, handleWorkDayChange,
    handleHardConstraintToggle,
    handleSoftConstraintToggle, handleSoftConstraintWeight, toggleAllConstraints,
    handleSoftConstraintTargetSubjects,
    handleAddCustomConstraint, handleUpdateCustomConstraint, handleDeleteCustomConstraint, handleToggleCustomConstraint,
    handleAddConstraintPattern, handleUpdateConstraintPattern, handleDeleteConstraintPattern,
    handleAddOtherDuty, handleUpdateOtherDuty, handleDeleteOtherDuty,
    fetchWorkloadSummary, handleWorkloadOverride,
    handleAddBreak, handleEditBreak, handleDeleteBreak, handleSaveBreak,
    handleAddUnavailability, handleSaveUnavailability, handleDeleteUnavailability, handleOpenNoorImport,
    loadClassAssignments, handleCreateClassAssignment, handleDeleteClassAssignment,
    subjectPickerRequest, subjectPickerSaving, cancelSubjectPicker, confirmSubjectPicker,
    toggleStageExpand, toggleTrackExpand, toggleGradeExpand,
    navigateToFix, setAssignments,
  };
}
