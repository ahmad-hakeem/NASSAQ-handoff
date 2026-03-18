import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import hakimEngine, { SYSTEM_EVENTS } from '../hakim/HakimContextEngine';

import { Sidebar } from '../../components/layout/Sidebar';
import TimetableGridSection from './TimetableGridSection';
import TimetableInsightsPanel from './TimetableInsightsPanel';
import TimetableVersionManager from './TimetableVersionManager';
import TimetableReadinessPanel from './TimetableReadinessPanel';
import HakimCharacter from './HakimCharacter';
import TimetableGenerationJourney from './TimetableGenerationJourney';
import {
  AITimetableGenerationModal,
  PublishTimetableVersionModal,
  TimetableSessionDetailsDrawer
} from './TimetableModals';

import { TimetableStatus, ReadinessStatus } from './types';
import { Skeleton } from '../../components/ui/skeleton';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Progress } from '../../components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { useAuth } from '../../contexts/AuthContext';
import {
  Calendar, GraduationCap, Users, Clock,
  Wand2, Send, Settings, Loader2, CheckCircle2,
  XCircle, RefreshCw,
  BookOpen, Coffee, Moon, Palette,
  CalendarDays, Sparkles, FileEdit, X, FilterX,
  Archive, ChevronDown, Eye, ArrowLeft, User, Hash,
  Printer, Download
} from 'lucide-react';

const buildHeaders = (token, schoolId) => ({
  'Content-Type': 'application/json',
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
  ...(schoolId && schoolId !== 'null' ? { 'X-School-Context': schoolId } : {})
});

const HakimAvatar = ({ size = 48, className = '' }) => (
  <div className={`relative ${className}`} style={{ width: size, height: size }}>
    <div className="absolute inset-0 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 shadow-lg animate-pulse" />
    <div className="absolute inset-[3px] rounded-full bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center">
      <Sparkles className="text-white" style={{ width: size * 0.45, height: size * 0.45 }} />
    </div>
    <div className="absolute -top-0.5 -right-0.5 w-3 h-3 bg-emerald-400 rounded-full border-2 border-white" />
  </div>
);

const DAY_NAMES_AR_MAP = {
  sunday: 'الأحد', monday: 'الاثنين', tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء', thursday: 'الخميس', friday: 'الجمعة', saturday: 'السبت'
};

const PreviousTimetableGrid = ({ data }) => {
  const [selectedClassId, setSelectedClassId] = useState(null);
  if (!data) return null;

  const { working_days = [], time_slots = [], classes = [], teachers = [], subjects = [], sessions = [] } = data;
  const teacherMap = Object.fromEntries((teachers || []).map(t => [t.id, t.full_name || t.name || '']));
  const subjectMap = Object.fromEntries((subjects || []).map(s => [s.id, s.name_ar || s.name || '']));

  const filteredClasses = selectedClassId
    ? classes.filter(c => c.id === selectedClassId)
    : classes;

  const sessionMap = {};
  for (const s of sessions) {
    const key = `${s.class_id}_${s.day_of_week}_${s.period_number}`;
    sessionMap[key] = s;
  }

  const PREV_DAY_COLORS = ['bg-violet-500', 'bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500', 'bg-cyan-500', 'bg-purple-500'];

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <select
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-violet-300"
          value={selectedClassId || ''}
          onChange={e => setSelectedClassId(e.target.value || null)}
        >
          <option value="">جميع الفصول ({classes.length})</option>
          {classes.map(c => (
            <option key={c.id} value={c.id}>{c.name_ar || c.name || c.id}</option>
          ))}
        </select>
      </div>

      {filteredClasses.map(cls => (
        <div key={cls.id} className="mb-6">
          <h3 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
            <GraduationCap className="h-4 w-4 text-violet-500" />
            {cls.name_ar || cls.name || cls.id}
          </h3>
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-xs" dir="rtl">
              <thead>
                <tr className="bg-gray-50">
                  <th className="p-2 text-gray-500 font-medium border-b border-gray-200 w-20">الفترة</th>
                  {working_days.map((day, di) => (
                    <th key={day} className="p-2 border-b border-gray-200">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-white text-[10px] font-bold ${PREV_DAY_COLORS[di % PREV_DAY_COLORS.length]}`}>
                        {DAY_NAMES_AR_MAP[day] || day}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {time_slots.map(slot => {
                  const isBreak = slot.is_break;
                  const isPrayer = slot.is_prayer;
                  if (isBreak || isPrayer) {
                    return (
                      <tr key={slot.period_number} className={isBreak ? 'bg-amber-50/60' : 'bg-sky-50/60'}>
                        <td className="p-1.5 text-center font-medium text-gray-400 border-b border-gray-100">
                          {slot.period_number}
                        </td>
                        <td colSpan={working_days.length} className="p-1.5 text-center border-b border-gray-100">
                          <span className={`text-[10px] font-medium ${isBreak ? 'text-amber-600' : 'text-sky-600'}`}>
                            {isBreak ? '☕ استراحة' : '🌙 صلاة'}
                          </span>
                        </td>
                      </tr>
                    );
                  }
                  return (
                    <tr key={slot.period_number} className="hover:bg-gray-50/50">
                      <td className="p-1.5 text-center font-medium text-gray-400 border-b border-gray-100">
                        {slot.period_number}
                      </td>
                      {working_days.map(day => {
                        const session = sessionMap[`${cls.id}_${day}_${slot.period_number}`];
                        if (!session) {
                          return (
                            <td key={day} className="p-1 border-b border-gray-100">
                              <div className="h-10 rounded-lg bg-gray-50 border border-dashed border-gray-200" />
                            </td>
                          );
                        }
                        return (
                          <td key={day} className="p-1 border-b border-gray-100">
                            <div className="h-10 rounded-lg bg-violet-50 border border-violet-100 flex flex-col items-center justify-center px-1">
                              <span className="text-[10px] font-semibold text-violet-700 truncate max-w-full">
                                {subjectMap[session.subject_id] || session.subject_name || '—'}
                              </span>
                              <span className="text-[9px] text-gray-400 truncate max-w-full">
                                {teacherMap[session.teacher_id] || session.teacher_name || ''}
                              </span>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
};

const ToggleCard = ({ active, onClick, icon: Icon, label, activeColor, activeBg, activeBorder }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl border-2 transition-all duration-200 select-none
      ${active
        ? `${activeBg} ${activeBorder} shadow-sm`
        : 'bg-gray-50 border-gray-200 hover:bg-gray-100 hover:border-gray-300'
      }`}
  >
    <div className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors
      ${active ? activeColor : 'bg-gray-200'}`}>
      <Icon className={`h-3.5 w-3.5 ${active ? 'text-white' : 'text-gray-500'}`} />
    </div>
    <span className={`text-sm font-medium ${active ? 'text-gray-800' : 'text-gray-500'}`}>{label}</span>
    <div className={`w-9 h-5 rounded-full relative transition-all duration-200 flex-shrink-0
      ${active ? activeColor : 'bg-gray-300'}`}>
      <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow-sm transition-all duration-200
        ${active ? 'right-0.5' : 'left-0.5'}`} />
    </div>
  </button>
);

const PLACEHOLDER_VALUE = '__none__';

const PrincipalTimetablePage = () => {
  const navigate = useNavigate();
  const { user, schoolContext } = useAuth();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const gridSectionRef = useRef(null);
  const journeyTimersRef = useRef([]);
  const [showSuccessOverlay, setShowSuccessOverlay] = useState(false);
  const genConfetti = useMemo(() => showSuccessOverlay ? Array.from({ length: 35 }, (_, i) => ({
    left: `${Math.random() * 100}%`, w: 8 + Math.random() * 12, h: 8 + Math.random() * 12,
    color: ['#46C1BE','#615090','#FFD700','#FF6B6B','#4ECDC4','#A855F7','#F97316','#3B82F6','#1C3D74','#10B981'][i % 10],
    radius: i % 3 === 0 ? '50%' : i % 3 === 1 ? '2px' : '0',
    dur: 2.5 + Math.random() * 3, delay: Math.random() * 2, rot: Math.random() * 360, endRot: 360 + Math.random() * 720,
  })) : [], [showSuccessOverlay]);
  const [successSessionsCount, setSuccessSessionsCount] = useState(0);
  const [showPublishSuccessOverlay, setShowPublishSuccessOverlay] = useState(false);
  const pubConfetti = useMemo(() => showPublishSuccessOverlay ? Array.from({ length: 35 }, (_, i) => ({
    left: `${Math.random() * 100}%`, w: 8 + Math.random() * 12, h: 8 + Math.random() * 12,
    color: ['#10B981','#46C1BE','#FFD700','#34D399','#6EE7B7','#A855F7','#3B82F6','#1C3D74','#F97316','#FF6B6B'][i % 10],
    radius: i % 3 === 0 ? '50%' : i % 3 === 1 ? '2px' : '0',
    dur: 2.5 + Math.random() * 3, delay: Math.random() * 2, rot: Math.random() * 360, endRot: 360 + Math.random() * 720,
  })) : [], [showPublishSuccessOverlay]);
  const [showGenerationJourney, setShowGenerationJourney] = useState(false);
  const [journeyApiCompleted, setJourneyApiCompleted] = useState(false);
  const [journeyApiFailed, setJourneyApiFailed] = useState(false);
  const [journeyErrorMessage, setJourneyErrorMessage] = useState('');

  useEffect(() => {
    return () => {
      journeyTimersRef.current.forEach(id => clearTimeout(id));
      journeyTimersRef.current = [];
    };
  }, []);

  const schoolId = useMemo(() => {
    if (schoolContext?.school_id) return schoolContext.school_id;
    if (user?.tenant_id) return user.tenant_id;
    if (user?.school_id) return user.school_id;
    if (user?.roles) {
      for (const r of user.roles) if (r.school_id) return r.school_id;
    }
    return localStorage.getItem('school_id') || localStorage.getItem('nassaq_school_id') || '';
  }, [user, schoolContext]);

  const token = localStorage.getItem('nassaq_token') || localStorage.getItem('token') || '';

  const [pageStatus, setPageStatus] = useState('loading');
  const [generationStatus, setGenerationStatus] = useState('idle');
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationMessage, setGenerationMessage] = useState('');

  const [selectedClassId, setSelectedClassId] = useState(null);
  const [selectedTeacherId, setSelectedTeacherId] = useState(null);
  const [selectedSubjectId, setSelectedSubjectId] = useState(null);
  const [selectedDayKey, setSelectedDayKey] = useState(null);

  const [showBreaks, setShowBreaks] = useState(true);
  const [showPrayer, setShowPrayer] = useState(true);
  const [showColorCoding, setShowColorCoding] = useState(true);

  const [summary, setSummary] = useState(null);
  const [readinessSummary, setReadinessSummary] = useState(null);
  const [timetableVersions, setTimetableVersions] = useState([]);
  const [activeVersion, setActiveVersion] = useState(null);
  const [filterOptions, setFilterOptions] = useState({
    classes: [], teachers: [], subjects: [], grades: [], time_slots: [], working_days: [], timetable_settings: {}
  });
  const [sessions, setSessions] = useState([]);
  const [gridLoading, setGridLoading] = useState(false);
  const [insights, setInsights] = useState(null);
  const [issues, setIssues] = useState([]);
  const [previousTimetables, setPreviousTimetables] = useState([]);
  const [showPreviousTimetables, setShowPreviousTimetables] = useState(false);
  const [viewingPreviousTT, setViewingPreviousTT] = useState(null);
  const [viewingPreviousLoading, setViewingPreviousLoading] = useState(false);

  const [modalState, setModalState] = useState({
    generationModalOpen: false,
    publishModalOpen: false,
    sessionDetailsOpen: false
  });
  const [selectedSession, setSelectedSession] = useState(null);
  const [modalSubmitting, setModalSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [conflictCells, setConflictCells] = useState([]);

  const api = useCallback(async (url, opts = {}) => {
    const res = await fetch(url, {
      ...opts,
      headers: { ...buildHeaders(token, schoolId), ...(opts.headers || {}) }
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(json?.detail || json?.message || `HTTP ${res.status}`);
    }
    return json;
  }, [token, schoolId]);

  const fetchSummary = useCallback(async () => {
    const data = await api('/api/principal/timetable/summary');
    setSummary(data.data || null);
    return data.data;
  }, [api]);

  const fetchReadiness = useCallback(async () => {
    const data = await api('/api/principal/timetable/readiness');
    setReadinessSummary(data.data || null);
    return data.data;
  }, [api]);

  const fetchVersions = useCallback(async () => {
    const data = await api('/api/principal/timetable/versions');
    const versions = data.data?.versions || [];
    setTimetableVersions(versions);
    const published = versions.find(v => v.status === 'published');
    const draft = versions.find(v => v.status === 'draft');
    const active = published || draft || null;
    setActiveVersion(active);
    return versions;
  }, [api]);

  const fetchFilterOptions = useCallback(async () => {
    const data = await api('/api/principal/timetable/filter-options');
    setFilterOptions(data.data || { classes: [], teachers: [], subjects: [], grades: [], time_slots: [], working_days: [], timetable_settings: {} });
    return data.data;
  }, [api]);

  const fetchGrid = useCallback(async (versionId, filters = {}, { silent = false } = {}) => {
    if (!silent) setGridLoading(true);
    try {
      const params = new URLSearchParams();
      if (versionId) params.set('timetable_id', versionId);
      if (filters.classId) params.set('class_id', filters.classId);
      if (filters.teacherId) params.set('teacher_id', filters.teacherId);
      if (filters.subjectId) params.set('subject_id', filters.subjectId);
      if (filters.day) params.set('day', filters.day);
      const data = await api(`/api/principal/timetable/grid?${params}`);
      setSessions(data.data?.sessions || []);
    } catch (err) {
      console.error('Grid fetch error:', err);
      if (!silent) setSessions([]);
    } finally {
      if (!silent) setGridLoading(false);
    }
  }, [api]);

  const fetchInsights = useCallback(async (versionId = null) => {
    try {
      const params = versionId ? `?timetable_id=${versionId}` : '';
      const data = await api(`/api/principal/timetable/insights${params}`);
      const raw = data.data?.insights || null;
      if (!raw) { setInsights(null); return; }
      setInsights({
        qualityScore: raw.quality_score ?? 0,
        totalRequiredSessions: raw.total_sessions ?? 0,
        totalAssignedSessions: raw.assigned_sessions ?? 0,
        totalUnassignedSessions: raw.unassigned_sessions ?? 0,
        warningsCount: raw.warnings_count ?? 0,
        hardConflictsCount: raw.conflicts_count ?? 0,
        coveragePercentage: raw.coverage_percentage ?? 0,
        dayDistribution: raw.day_distribution ?? {},
        subjectDistribution: raw.subject_distribution ?? {},
        quality_score: raw.quality_score ?? 0,
        warnings_count: raw.warnings_count ?? 0,
      });
    } catch (err) {
      console.error('Insights fetch error:', err);
    }
  }, [api]);

  const fetchIssues = useCallback(async (versionId = null) => {
    try {
      const params = versionId ? `?timetable_id=${versionId}` : '';
      const data = await api(`/api/principal/timetable/issues${params}`);
      setIssues(data.data?.issues || []);
    } catch (err) {
      console.error('Issues fetch error:', err);
    }
  }, [api]);

  const fetchPreviousTimetables = useCallback(async () => {
    try {
      const data = await api('/api/principal/timetable/previous');
      setPreviousTimetables(data.data?.previous_timetables || []);
    } catch (err) {
      console.error('Previous timetables fetch error:', err);
    }
  }, [api]);

  const viewPreviousTimetable = useCallback(async (ttId) => {
    setViewingPreviousLoading(true);
    try {
      const data = await api(`/api/principal/timetable/previous/${ttId}/view`);
      setViewingPreviousTT(data.data || null);
    } catch (err) {
      nassaqError('فشل في تحميل الجدول السابق');
      console.error('View previous timetable error:', err);
    } finally {
      setViewingPreviousLoading(false);
    }
  }, [api]);

  const loadPageData = useCallback(async () => {
    setPageStatus('loading');
    setErrorMessage(null);
    try {
      const [, , versions] = await Promise.all([
        fetchSummary(),
        fetchReadiness(),
        fetchVersions(),
        fetchFilterOptions()
      ]);

      const versionForGrid = versions?.find(v => v.status === 'published') ||
                             versions?.find(v => v.status === 'draft') || null;

      if (versionForGrid) {
        await Promise.all([
          fetchGrid(versionForGrid.id, {}),
          fetchInsights(versionForGrid.id),
          fetchIssues(versionForGrid.id)
        ]);
      }
      setPageStatus('ready');
    } catch (err) {
      console.error('Page load error:', err);
      setErrorMessage(err.message);
      setPageStatus('error');
    }
  }, [fetchSummary, fetchReadiness, fetchVersions, fetchFilterOptions, fetchGrid, fetchInsights, fetchIssues]);

  useEffect(() => {
    if (schoolId) loadPageData();
  }, [schoolId]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentFilters = useMemo(() => ({
    classId: selectedClassId,
    teacherId: selectedTeacherId,
    subjectId: selectedSubjectId,
    day: selectedDayKey,
  }), [selectedClassId, selectedTeacherId, selectedSubjectId, selectedDayKey]);

  const activeFilterCount = useMemo(() =>
    [selectedClassId, selectedTeacherId, selectedSubjectId, selectedDayKey].filter(Boolean).length,
    [selectedClassId, selectedTeacherId, selectedSubjectId, selectedDayKey]
  );

  useEffect(() => {
    if (!activeVersion || pageStatus !== 'ready') return;
    fetchGrid(activeVersion.id, currentFilters);
  }, [currentFilters, activeVersion?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleClearAllFilters = () => {
    setSelectedClassId(null);
    setSelectedTeacherId(null);
    setSelectedSubjectId(null);
    setSelectedDayKey(null);
    setConflictCells([]);
  };

  const handleGenerateTimetable = async (options = {}) => {
    setModalSubmitting(true);
    setGenerationStatus('running');
    setGenerationProgress(0);
    setGenerationMessage('جاري تحضير البيانات...');

    setJourneyApiCompleted(false);
    setJourneyApiFailed(false);
    setJourneyErrorMessage('');
    setShowGenerationJourney(true);

    try {
      setModalState(prev => ({ ...prev, generationModalOpen: false }));

      const result = await api('/api/principal/timetable/generate', {
        method: 'POST',
        body: JSON.stringify({
          generation_mode: options.generationMode || 'full',
          constraints: options.constraints || {}
        })
      });

      setGenerationProgress(100);
      setGenerationMessage('تم توليد الجدول بنجاح!');

      const sessionsCount = result.data?.sessions_count || result.data?.result?.sessions_count || 0;
      setSuccessSessionsCount(sessionsCount);

      await Promise.all([
        fetchSummary(),
        fetchVersions(),
        fetchFilterOptions()
      ]);

      const newVersions = await api('/api/principal/timetable/versions');
      const vs = newVersions.data?.versions || [];
      const newest = vs[0];
      if (newest) {
        setActiveVersion(newest);
        handleClearAllFilters();
        await Promise.all([
          fetchGrid(newest.id, {}),
          fetchInsights(newest.id),
          fetchIssues(newest.id)
        ]);
      }

      setJourneyApiCompleted(true);
      hakimEngine.fireEvent(SYSTEM_EVENTS.SCHEDULE_CREATED);

      const t1 = setTimeout(() => {
        setShowGenerationJourney(false);
        setGenerationStatus('idle');
        setShowSuccessOverlay(true);
        const t2 = setTimeout(() => {
          setShowSuccessOverlay(false);
          const t3 = setTimeout(() => {
            gridSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 300);
          journeyTimersRef.current.push(t3);
        }, 2500);
        journeyTimersRef.current.push(t2);
      }, 2800);
      journeyTimersRef.current.push(t1);
    } catch (err) {
      setJourneyApiFailed(true);
      setJourneyErrorMessage(err.message || 'فشل في توليد الجدول');
      setGenerationStatus('failed');
      setGenerationMessage(err.message || 'فشل في توليد الجدول');
    } finally {
      setModalSubmitting(false);
    }
  };

  const clearJourneyTimers = () => {
    journeyTimersRef.current.forEach(id => clearTimeout(id));
    journeyTimersRef.current = [];
  };

  const handleJourneyRetry = () => {
    clearJourneyTimers();
    setShowGenerationJourney(false);
    setGenerationStatus('idle');
    const t = setTimeout(() => {
      setModalState(prev => ({ ...prev, generationModalOpen: true }));
    }, 300);
    journeyTimersRef.current.push(t);
  };

  const handleJourneyClose = () => {
    clearJourneyTimers();
    setShowGenerationJourney(false);
    setGenerationStatus('idle');
  };

  const handlePublishVersion = async () => {
    if (!activeVersion) return;
    setModalSubmitting(true);
    try {
      const publishedVersionId = activeVersion.id;
      await api(`/api/principal/timetable/version/${publishedVersionId}/publish`, { method: 'POST' });
      setModalState(prev => ({ ...prev, publishModalOpen: false }));
      const versions = await fetchVersions();
      await fetchSummary();
      const published = versions?.find(v => v.id === publishedVersionId);
      if (published) {
        setActiveVersion({ ...published, status: 'published', is_published: true });
      } else {
        setActiveVersion(prev => ({ ...prev, status: 'published', is_published: true }));
      }
      setSelectedClassId(null);
      setSelectedTeacherId(null);
      setSelectedSubjectId(null);
      setSelectedDayKey(null);
      await fetchGrid(publishedVersionId, {});
      hakimEngine.fireEvent(SYSTEM_EVENTS.TIMETABLE_PUBLISHED);
      setShowPublishSuccessOverlay(true);
      setTimeout(() => {
        setShowPublishSuccessOverlay(false);
      }, 3000);
    } catch (err) {
      nassaqError(`فشل النشر: ${err.message}`);
    } finally {
      setModalSubmitting(false);
    }
  };

  const handleVersionSelect = async (versionId) => {
    const version = timetableVersions.find(v => v.id === versionId);
    if (version) {
      setActiveVersion(version);
      await Promise.all([
        fetchGrid(versionId, currentFilters),
        fetchInsights(versionId),
        fetchIssues(versionId)
      ]);
    }
  };

  const handleSessionClick = (session) => {
    setSelectedSession(session);
    setModalState(prev => ({ ...prev, sessionDetailsOpen: true }));
  };

  const handleSessionSwap = async (sessionId1, sessionId2) => {
    const prevSessions = [...sessions];
    const s1 = sessions.find(s => s.id === sessionId1);
    const s2 = sessions.find(s => s.id === sessionId2);

    if (s1 && s2) {
      const s1Day = s1.day_of_week || s1.day;
      const s1Period = s1.period_number;
      const s1Slot = s1.time_slot_id;
      const s1Start = s1.start_time;
      const s1End = s1.end_time;

      setSessions(prev => prev.map(s => {
        if (s.id === sessionId1) {
          return {
            ...s,
            day_of_week: s2.day_of_week || s2.day,
            day: s2.day_of_week || s2.day,
            period_number: s2.period_number,
            time_slot_id: s2.time_slot_id,
            start_time: s2.start_time,
            end_time: s2.end_time,
            _justMoved: true
          };
        }
        if (s.id === sessionId2) {
          return {
            ...s,
            day_of_week: s1Day,
            day: s1Day,
            period_number: s1Period,
            time_slot_id: s1Slot,
            start_time: s1Start,
            end_time: s1End,
            _justMoved: true
          };
        }
        return s;
      }));
    }

    try {
      const result = await api('/api/principal/timetable/sessions/swap', {
        method: 'POST',
        body: JSON.stringify({ session_id_1: sessionId1, session_id_2: sessionId2 })
      });
      if (result.success) {
        toast.success('تم تبديل الحصتين بنجاح');
        hakimEngine.fireEvent(SYSTEM_EVENTS.TASK_COMPLETED, 'تم تبديل الحصتين بنجاح!');
        if (activeVersion) fetchGrid(activeVersion.id, currentFilters, { silent: true });
      } else {
        setSessions(prevSessions);
        nassaqWarning(result.detail || result.message || 'فشل تبديل الحصتين');
      }
    } catch (err) {
      setSessions(prevSessions);
      nassaqWarning(err.message || 'فشل تبديل الحصتين');
    }
  };

  const handleSessionMove = async (sessionId, newDay, newPeriod) => {
    const prevSessions = [...sessions];
    const movedSession = sessions.find(s => s.id === sessionId);

    if (movedSession) {
      const matchingSlot = (filterOptions.time_slots || []).find(
        ts => ts.period_number != null && Number(ts.period_number) === Number(newPeriod) &&
              ts.type !== 'break' && ts.type !== 'prayer'
      ) || (filterOptions.time_slots || []).find(
        ts => Number(ts.slot_number) === Number(newPeriod) &&
              ts.type !== 'break' && ts.type !== 'prayer'
      );
      setSessions(prev => prev.map(s => {
        if (s.id === sessionId) {
          return {
            ...s,
            day_of_week: newDay,
            day: newDay,
            period_number: Number(newPeriod),
            time_slot_id: matchingSlot?.id || s.time_slot_id,
            start_time: matchingSlot?.start_time || s.start_time,
            end_time: matchingSlot?.end_time || s.end_time,
            _justMoved: true
          };
        }
        return s;
      }));
    }

    try {
      const result = await api('/api/principal/timetable/sessions/move', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, new_day: newDay, new_period: Number(newPeriod) })
      });
      if (result.success) {
        toast.success('تم نقل الحصة بنجاح');
        hakimEngine.fireEvent(SYSTEM_EVENTS.TASK_COMPLETED, 'تم نقل الحصة بنجاح!');
        if (activeVersion) fetchGrid(activeVersion.id, currentFilters, { silent: true });
      } else {
        setSessions(prevSessions);
        nassaqWarning(result.detail || result.message || 'فشل نقل الحصة');
      }
    } catch (err) {
      setSessions(prevSessions);
      nassaqWarning(err.message || 'فشل نقل الحصة');
    }
  };

  const handleExportCSV = () => {
    if (!sessions?.length) {
      nassaqWarning('لا توجد بيانات للتصدير');
      return;
    }
    const escCSV = (v) => {
      const s = String(v ?? '');
      return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const teacherLookup = Object.fromEntries((filterOptions.teachers || []).map(t => [t.id, t.full_name || t.name || '']));
    const subjectLookup = Object.fromEntries((filterOptions.subjects || []).map(s => [s.id, s.name_ar || s.name || '']));
    const classLookup = Object.fromEntries((filterOptions.classes || []).map(c => [c.id, c.name_ar || c.name || '']));
    const rows = [['اليوم', 'الفترة', 'المادة', 'المعلم', 'الفصل', 'الوقت'].map(escCSV).join(',')];
    for (const s of sessions) {
      rows.push([
        escCSV(DAY_NAMES_AR_MAP[s.day_of_week] || s.day_of_week),
        escCSV(s.period_number),
        escCSV(subjectLookup[s.subject_id] || s.subject_name || ''),
        escCSV(teacherLookup[s.teacher_id] || s.teacher_name || ''),
        escCSV(classLookup[s.class_id] || s.class_name || ''),
        escCSV(`${s.start_time || ''}-${s.end_time || ''}`)
      ].join(','));
    }
    const BOM = '\uFEFF';
    const csv = BOM + rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `timetable_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('تم تصدير الجدول بنجاح');
    hakimEngine.fireEvent(SYSTEM_EVENTS.DATA_EXPORTED);
  };

  const getCurrentStatus = () => {
    if (generationStatus === 'running') return TimetableStatus.GENERATING;
    if (generationStatus === 'failed') return TimetableStatus.FAILED;
    if (!activeVersion) return TimetableStatus.NONE;
    return activeVersion.status === 'published' ? TimetableStatus.PUBLISHED : TimetableStatus.DRAFT;
  };

  const canGenerate = (
    readinessSummary?.can_generate === true ||
    readinessSummary?.overall_status === 'FULLY_READY' ||
    readinessSummary?.overall_status === 'PARTIALLY_READY'
  ) && generationStatus !== 'running';

  const hasDraft = timetableVersions.some(v => v.status === 'draft');
  const classes = filterOptions.classes || [];
  const teachers = filterOptions.teachers || [];
  const subjects = filterOptions.subjects || [];
  const timeSlots = filterOptions.time_slots || [];
  const workingDays = filterOptions.working_days || [];
  const timetableSettings = filterOptions.timetable_settings || {};

  const teachingSlots = timeSlots.filter(s => !s.is_break && !s.is_prayer && s.type !== 'prayer' && s.type !== 'break');

  const currentStatus = getCurrentStatus();

  const DAY_NAMES = { sunday: 'الأحد', monday: 'الاثنين', tuesday: 'الثلاثاء', wednesday: 'الأربعاء', thursday: 'الخميس', friday: 'الجمعة', saturday: 'السبت' };

  const activeFilterLabels = useMemo(() => {
    const labels = [];
    if (selectedClassId) {
      const cls = classes.find(c => c.id === selectedClassId);
      if (cls) labels.push({ key: 'class', label: cls.name, icon: GraduationCap, color: 'bg-blue-100 text-blue-700 border-blue-200', clear: () => setSelectedClassId(null) });
    }
    if (selectedTeacherId) {
      const tch = teachers.find(t => t.id === selectedTeacherId);
      if (tch) labels.push({ key: 'teacher', label: tch.name, icon: Users, color: 'bg-violet-100 text-violet-700 border-violet-200', clear: () => setSelectedTeacherId(null) });
    }
    if (selectedSubjectId) {
      const sub = subjects.find(s => s.id === selectedSubjectId);
      if (sub) labels.push({ key: 'subject', label: sub.name, icon: BookOpen, color: 'bg-emerald-100 text-emerald-700 border-emerald-200', clear: () => setSelectedSubjectId(null) });
    }
    if (selectedDayKey) {
      labels.push({ key: 'day', label: DAY_NAMES[selectedDayKey] || selectedDayKey, icon: Calendar, color: 'bg-rose-100 text-rose-700 border-rose-200', clear: () => setSelectedDayKey(null) });
    }
    return labels;
  }, [selectedClassId, selectedTeacherId, selectedSubjectId, selectedDayKey, classes, teachers, subjects]);

  const filterType = useMemo(() => {
    if (activeFilterCount === 0) return 'all';
    if (activeFilterCount === 1) {
      if (selectedClassId) return 'class';
      if (selectedTeacherId) return 'teacher';
      if (selectedSubjectId) return 'subject';
      if (selectedDayKey) return 'day';
    }
    return 'multi';
  }, [activeFilterCount, selectedClassId, selectedTeacherId, selectedSubjectId, selectedDayKey]);

  if (pageStatus === 'loading') {
    return (
      <Sidebar>
        <div className="min-h-screen bg-gradient-to-bl from-slate-50 via-white to-blue-50/30" dir="rtl">
          <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
            <Skeleton className="h-32 w-full rounded-2xl" />
            <Skeleton className="h-20 w-full rounded-2xl" />
            <Skeleton className="h-[500px] w-full rounded-2xl" />
          </div>
        </div>
      </Sidebar>
    );
  }

  if (pageStatus === 'error') {
    return (
      <Sidebar>
        <div className="min-h-screen bg-gradient-to-bl from-slate-50 via-white to-blue-50/30" dir="rtl">
          <div className="p-6 max-w-[1400px] mx-auto flex flex-col items-center justify-center py-20">
            <div className="w-20 h-20 rounded-full bg-red-100 flex items-center justify-center mb-6">
              <XCircle className="h-10 w-10 text-red-500" />
            </div>
            <h2 className="text-xl font-bold text-red-700 mb-2">حدث خطأ في تحميل الصفحة</h2>
            <p className="text-red-600 mb-6 text-center max-w-md">{errorMessage}</p>
            <Button onClick={loadPageData} className="bg-brand-navy hover:bg-brand-navy/90 gap-2">
              <RefreshCw className="h-4 w-4" />
              إعادة المحاولة
            </Button>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-bl from-slate-50 via-white to-blue-50/30" dir="rtl">
        <div className="p-4 lg:p-6 space-y-5 max-w-[1400px] mx-auto">

          {/* ═══════════════ HERO HEADER ═══════════════ */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-l from-[#1a1f4e] via-[#252b6e] to-[#2d3594] p-6 text-white shadow-xl">
            <div className="absolute inset-0 nassaq-pattern opacity-[0.05]" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
            <div className="absolute inset-0 opacity-10">
              <div className="absolute top-0 left-0 w-40 h-40 bg-white/20 rounded-full -translate-x-1/2 -translate-y-1/2" />
              <div className="absolute bottom-0 right-0 w-60 h-60 bg-white/10 rounded-full translate-x-1/4 translate-y-1/4" />
            </div>
            <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur-sm flex items-center justify-center border border-white/20">
                  <Calendar className="h-7 w-7 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold">الجدول المدرسي</h1>
                  <div className="flex items-center gap-2 text-white/70 text-sm mt-1">
                    {summary?.school_name && <span>{summary.school_name}</span>}
                    {summary?.academic_year && (
                      <>
                        <span className="text-white/30">|</span>
                        <span>{summary.academic_year}</span>
                      </>
                    )}
                    {summary?.current_semester && (
                      <>
                        <span className="text-white/30">|</span>
                        <span>{summary.current_semester}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1.5 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-1.5 border border-white/10">
                  <GraduationCap className="h-4 w-4 text-emerald-300" />
                  <span className="text-sm font-medium">{classes.length} فصل</span>
                </div>
                <div className="flex items-center gap-1.5 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-1.5 border border-white/10">
                  <Users className="h-4 w-4 text-sky-300" />
                  <span className="text-sm font-medium">{teachers.length} معلم</span>
                </div>
                <div className="flex items-center gap-1.5 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-1.5 border border-white/10">
                  <Clock className="h-4 w-4 text-amber-300" />
                  <span className="text-sm font-medium">{teachingSlots.length || timetableSettings.periods_per_day || 0} حصة يومياً</span>
                </div>

                {currentStatus === TimetableStatus.PUBLISHED && (
                  <Badge className="bg-emerald-500/20 text-emerald-200 border border-emerald-400/30 gap-1 text-sm px-3 py-1">
                    <CheckCircle2 className="h-3.5 w-3.5" /> منشور
                  </Badge>
                )}
                {currentStatus === TimetableStatus.DRAFT && (
                  <Badge className="bg-amber-500/20 text-amber-200 border border-amber-400/30 gap-1 text-sm px-3 py-1">
                    <FileEdit className="h-3.5 w-3.5" /> مسودة
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {/* ═══════════════ DRAFT STATUS BANNER ═══════════════ */}
          {currentStatus === TimetableStatus.DRAFT && (
            <Card className="border-2 border-amber-300 bg-gradient-to-l from-amber-50 via-yellow-50 to-orange-50 shadow-md overflow-hidden">
              <CardContent className="p-0">
                <div className="flex items-center justify-between p-5">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center border border-amber-200">
                      <FileEdit className="h-6 w-6 text-amber-600" />
                    </div>
                    <div>
                      <h3 className="font-bold text-amber-900 text-base">هذا الجدول لا يزال مسودة ولم يتم نشره بعد</h3>
                      <p className="text-amber-700 text-sm mt-0.5">تم توليد الجدول بنجاح ويحتاج إلى النشر ليصبح فعالاً ومتاحاً للجميع</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="hidden lg:flex items-center gap-2 ml-4">
                      <HakimCharacter state="success" size="sm" showMessage={false} />
                      <div className="relative bg-white rounded-xl px-3 py-2 shadow-sm border border-amber-200">
                        <div className="absolute -right-1.5 top-3 w-3 h-3 bg-white border-r border-b border-amber-200 rotate-45" />
                        <p className="text-xs text-amber-800 font-medium">انشر الجدول ليصبح متاحاً!</p>
                      </div>
                    </div>
                    <Button
                      onClick={() => setModalState(prev => ({ ...prev, publishModalOpen: true }))}
                      className="bg-gradient-to-l from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white shadow-lg hover:shadow-xl transition-all px-6 py-3 text-sm font-bold gap-2 h-auto"
                    >
                      <Send className="h-5 w-5" />
                      نشر الجدول الآن
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ═══════════════ PUBLISHED STATUS BANNER ═══════════════ */}
          {currentStatus === TimetableStatus.PUBLISHED && (
            <Card className="border-2 border-emerald-300 bg-gradient-to-l from-emerald-50 via-green-50 to-teal-50 shadow-md overflow-hidden">
              <CardContent className="p-0">
                <div className="flex items-center justify-between p-5">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center border border-emerald-200">
                      <CheckCircle2 className="h-6 w-6 text-emerald-600" />
                    </div>
                    <div>
                      <h3 className="font-bold text-emerald-900 text-base flex items-center gap-2">
                        الجدول الحالي: منشور ومعتمد
                        <span className="text-emerald-500">✔</span>
                      </h3>
                      <p className="text-emerald-700 text-sm mt-0.5">
                        {activeVersion?.published_at
                          ? `تم النشر بتاريخ ${new Date(activeVersion.published_at).toLocaleDateString('ar-SA', { year: 'numeric', month: 'long', day: 'numeric' })}${activeVersion.published_by_name ? ` بواسطة ${activeVersion.published_by_name}` : ''}`
                          : 'هذا هو الجدول الرسمي المعتمد والمتاح للجميع'}
                      </p>
                    </div>
                  </div>
                  <div className="hidden lg:flex items-center gap-2">
                    <HakimCharacter state="success" size="sm" showMessage={false} />
                    <div className="relative bg-white rounded-xl px-3 py-2 shadow-sm border border-emerald-200">
                      <div className="absolute -right-1.5 top-3 w-3 h-3 bg-white border-r border-b border-emerald-200 rotate-45" />
                      <p className="text-xs text-emerald-800 font-medium">الجدول نشط ومعتمد!</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ═══════════════ STATUS BANNER (failed only — generating uses journey overlay) ═══════════════ */}
          {currentStatus === TimetableStatus.FAILED && !showGenerationJourney && (
            <Card className="border-red-200 bg-gradient-to-l from-red-50 to-rose-50">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <XCircle className="h-6 w-6 text-red-500" />
                    <div>
                      <h3 className="font-bold text-red-800">فشل في معالجة الجدول</h3>
                      {generationMessage && <p className="text-red-600 text-sm">{generationMessage}</p>}
                    </div>
                  </div>
                  <Button onClick={() => setModalState(prev => ({ ...prev, generationModalOpen: true }))} className="bg-red-600 hover:bg-red-700 gap-2">
                    <RefreshCw className="h-4 w-4" /> إعادة المحاولة
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ═══════════════ HAKIM CTA: Generate Timetable ═══════════════ */}
          <Card className="border-2 border-violet-200 bg-gradient-to-l from-violet-50 via-purple-50 to-indigo-50 shadow-lg overflow-hidden print:hidden">
            <CardContent className="p-0">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 p-5">
                <div className="flex items-center gap-4">
                  <div className="relative flex-shrink-0 cursor-pointer" onClick={() => {
                    if (canGenerate && generationStatus !== 'running') {
                      setModalState(prev => ({ ...prev, generationModalOpen: true }));
                    }
                  }}>
                    <HakimCharacter
                      state={generationStatus === 'running' ? 'generating' : generationStatus === 'failed' ? 'error' : currentStatus === TimetableStatus.DRAFT ? 'success' : 'idle'}
                      size="lg"
                      showMessage={false}
                    />
                    {canGenerate && generationStatus !== 'running' && (
                      <div className="absolute -bottom-1 -left-1 w-5 h-5 rounded-full bg-emerald-400 border-2 border-white flex items-center justify-center">
                        <Sparkles className="h-3 w-3 text-white" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="relative bg-white rounded-xl px-4 py-3 shadow-sm border border-violet-200">
                      <div className="absolute -right-1.5 top-4 w-3 h-3 bg-white border-r border-b border-violet-200 rotate-45 hidden lg:block" />
                      <p className="text-sm text-violet-800 font-tajawal font-bold leading-relaxed">
                        {generationStatus === 'running'
                          ? 'أعمل الآن على إنشاء الجدول... انتظر قليلاً! ⏳'
                          : generationStatus === 'failed'
                          ? 'واجهت مشكلة في المرة السابقة. هل نحاول مرة أخرى؟'
                          : canGenerate
                          ? 'مرحباً! أنا حكيم. اضغط الزر وسأبدأ ببناء أفضل جدول دراسي ممكن! ✨'
                          : 'أحتاج إلى إكمال متطلبات الجاهزية أولاً قبل بناء الجدول.'}
                      </p>
                      <p className="text-xs text-violet-500 mt-1 font-tajawal">
                        {canGenerate
                          ? 'سأراجع البيانات والقيود وأوزّع الحصص بذكاء'
                          : 'راجع لوحة الجاهزية بالأسفل لمعرفة المتطلبات الناقصة'}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col items-stretch lg:items-end gap-2 flex-shrink-0">
                  <button
                    onClick={() => setModalState(prev => ({ ...prev, generationModalOpen: true }))}
                    disabled={!canGenerate || generationStatus === 'running'}
                    className={`group relative flex items-center justify-center gap-3 px-8 py-4 rounded-2xl font-bold text-base transition-all duration-300 ${
                      canGenerate && generationStatus !== 'running'
                        ? 'bg-gradient-to-l from-violet-600 via-purple-600 to-indigo-600 hover:from-violet-700 hover:via-purple-700 hover:to-indigo-700 text-white shadow-xl hover:shadow-2xl hover:shadow-violet-500/30 hover:scale-[1.03] active:scale-[0.98]'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                  >
                    {canGenerate && generationStatus !== 'running' && (
                      <div className="absolute inset-0 rounded-2xl bg-gradient-to-l from-violet-400 to-purple-400 opacity-0 group-hover:opacity-20 transition-opacity duration-300" />
                    )}
                    {generationStatus === 'running' ? (
                      <><Loader2 className="h-6 w-6 animate-spin" /> جاري إنشاء الجدول...</>
                    ) : (
                      <><Wand2 className="h-6 w-6" /> توليد الجدول بالذكاء الاصطناعي</>
                    )}
                  </button>
                  <div className="flex items-center justify-center lg:justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => navigate('/school/settings')} className="gap-1.5 text-xs text-gray-500 hover:text-gray-700 h-8">
                      <Settings className="h-3.5 w-3.5" /> الإعدادات
                    </Button>
                    {(currentStatus === TimetableStatus.DRAFT || currentStatus === TimetableStatus.PUBLISHED) && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => window.print()} className="gap-1.5 text-xs text-gray-500 hover:text-gray-700 h-8" data-testid="print-timetable-btn">
                          <Printer className="h-3.5 w-3.5" /> طباعة
                        </Button>
                        <Button variant="ghost" size="sm" onClick={handleExportCSV} className="gap-1.5 text-xs text-gray-500 hover:text-gray-700 h-8" data-testid="export-timetable-btn">
                          <Download className="h-3.5 w-3.5" /> تصدير
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ═══════════════ READINESS ═══════════════ */}
          <TimetableReadinessPanel
            items={readinessSummary?.items || []}
            categories={readinessSummary?.phases || {}}
            phases={readinessSummary?.phases || {}}
            overallStatus={readinessSummary?.overall_status || ReadinessStatus.NOT_READY}
            percentage={readinessSummary?.percentage || 0}
            currentPhase={readinessSummary?.current_phase || 1}
            criticalIssuesCount={readinessSummary?.summary?.critical_count || 0}
            warningsCount={readinessSummary?.summary?.warning_count || 0}
            canGenerate={canGenerate}
            capacity={readinessSummary?.capacity || null}
            onFixItem={(key, link) => { if (link) navigate(link); }}
            onRefresh={async () => {
              await fetchReadiness();
              toast.info('تم تحديث حالة الجاهزية');
            }}
          />

          {/* ═══════════════ MULTI-FILTER CONTROLS ═══════════════ */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-gray-100">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <CalendarDays className="h-5 w-5 text-gray-600" />
                  <span className="text-sm font-bold text-gray-700">تصفية الجدول</span>
                  {activeFilterCount > 0 && (
                    <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs px-2">
                      {activeFilterCount} {activeFilterCount === 1 ? 'فلتر' : 'فلاتر'}
                    </Badge>
                  )}
                </div>
                {activeFilterCount > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearAllFilters}
                    className="text-red-500 hover:text-red-700 hover:bg-red-50 gap-1.5 text-xs"
                  >
                    <FilterX className="h-3.5 w-3.5" />
                    إلغاء جميع الفلاتر
                  </Button>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {/* Class Filter */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-500">
                    <GraduationCap className="h-3.5 w-3.5 text-blue-500" />
                    الفصل
                  </label>
                  <Select
                    value={selectedClassId || PLACEHOLDER_VALUE}
                    onValueChange={(val) => setSelectedClassId(val === PLACEHOLDER_VALUE ? null : val)}
                  >
                    <SelectTrigger className={`w-full h-10 rounded-xl text-sm font-medium transition-all ${
                      selectedClassId
                        ? 'bg-blue-50 border-blue-300 ring-1 ring-blue-200'
                        : 'bg-gray-50 border-gray-200'
                    }`}>
                      <SelectValue placeholder="جميع الفصول" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={PLACEHOLDER_VALUE}>جميع الفصول</SelectItem>
                      {classes.map(c => (
                        <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Teacher Filter */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-500">
                    <Users className="h-3.5 w-3.5 text-violet-500" />
                    المعلم
                  </label>
                  <Select
                    value={selectedTeacherId || PLACEHOLDER_VALUE}
                    onValueChange={(val) => setSelectedTeacherId(val === PLACEHOLDER_VALUE ? null : val)}
                  >
                    <SelectTrigger className={`w-full h-10 rounded-xl text-sm font-medium transition-all ${
                      selectedTeacherId
                        ? 'bg-violet-50 border-violet-300 ring-1 ring-violet-200'
                        : 'bg-gray-50 border-gray-200'
                    }`}>
                      <SelectValue placeholder="جميع المعلمين" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={PLACEHOLDER_VALUE}>جميع المعلمين</SelectItem>
                      {teachers.map(t => (
                        <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Subject Filter */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-500">
                    <BookOpen className="h-3.5 w-3.5 text-emerald-500" />
                    المادة
                  </label>
                  <Select
                    value={selectedSubjectId || PLACEHOLDER_VALUE}
                    onValueChange={(val) => setSelectedSubjectId(val === PLACEHOLDER_VALUE ? null : val)}
                  >
                    <SelectTrigger className={`w-full h-10 rounded-xl text-sm font-medium transition-all ${
                      selectedSubjectId
                        ? 'bg-emerald-50 border-emerald-300 ring-1 ring-emerald-200'
                        : 'bg-gray-50 border-gray-200'
                    }`}>
                      <SelectValue placeholder="جميع المواد" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={PLACEHOLDER_VALUE}>جميع المواد</SelectItem>
                      {subjects.map(s => (
                        <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Day Filter */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-500">
                    <Calendar className="h-3.5 w-3.5 text-rose-500" />
                    اليوم
                  </label>
                  <Select
                    value={selectedDayKey || PLACEHOLDER_VALUE}
                    onValueChange={(val) => setSelectedDayKey(val === PLACEHOLDER_VALUE ? null : val)}
                  >
                    <SelectTrigger className={`w-full h-10 rounded-xl text-sm font-medium transition-all ${
                      selectedDayKey
                        ? 'bg-rose-50 border-rose-300 ring-1 ring-rose-200'
                        : 'bg-gray-50 border-gray-200'
                    }`}>
                      <SelectValue placeholder="جميع الأيام" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={PLACEHOLDER_VALUE}>جميع الأيام</SelectItem>
                      {workingDays.map(d => (
                        <SelectItem key={d.key} value={d.key}>{d.name_ar}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Active Filters Chips + Toggle Controls */}
            <div className="p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                {activeFilterCount === 0 ? (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <CalendarDays className="h-4 w-4" />
                    <span>عرض الجدول الكامل</span>
                    <span className="text-gray-300">•</span>
                    <span className="font-medium text-gray-500">{sessions.length} حصة</span>
                  </div>
                ) : (
                  <>
                    {activeFilterLabels.map(f => {
                      const Icon = f.icon;
                      return (
                        <div
                          key={f.key}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold ${f.color}`}
                        >
                          <Icon className="h-3 w-3" />
                          <span>{f.label}</span>
                          <button
                            onClick={f.clear}
                            className="ml-1 hover:bg-black/10 rounded-full p-0.5 transition-colors"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      );
                    })}
                    <span className="text-gray-300">•</span>
                    <span className="text-xs font-medium text-gray-500">{sessions.length} حصة</span>
                  </>
                )}
              </div>

              {/* Toggle Controls */}
              <div className="flex items-center gap-3">
                <ToggleCard
                  active={showBreaks}
                  onClick={() => setShowBreaks(!showBreaks)}
                  icon={Coffee}
                  label="الاستراحة"
                  activeColor="bg-amber-500"
                  activeBg="bg-amber-50"
                  activeBorder="border-amber-300"
                />
                <ToggleCard
                  active={showPrayer}
                  onClick={() => setShowPrayer(!showPrayer)}
                  icon={Moon}
                  label="الصلاة"
                  activeColor="bg-emerald-500"
                  activeBg="bg-emerald-50"
                  activeBorder="border-emerald-300"
                />
                <ToggleCard
                  active={showColorCoding}
                  onClick={() => setShowColorCoding(!showColorCoding)}
                  icon={Palette}
                  label="ألوان المواد"
                  activeColor="bg-violet-500"
                  activeBg="bg-violet-50"
                  activeBorder="border-violet-300"
                />
              </div>
            </div>
          </div>

          {/* ═══════════════ GRID (FULL WIDTH) ═══════════════ */}
          <div ref={gridSectionRef} />
          <TimetableGridSection
            loading={gridLoading}
            hasData={sessions.length > 0 || timeSlots.length > 0}
            activeViewMode={filterType === 'all' ? 'all' : filterType}
            workingDays={workingDays.map(d => ({ key: d.key, ar: d.name_ar, label: d.name_ar, ...d }))}
            timeSlots={timeSlots}
            sessions={sessions}
            selectedFilter={selectedClassId || selectedTeacherId || selectedSubjectId || selectedDayKey}
            filterType={filterType}
            showBreaks={showBreaks}
            showPrayer={showPrayer}
            showWarnings={true}
            showColorCoding={showColorCoding}
            conflictCells={conflictCells}
            onSessionClick={handleSessionClick}
            onGenerate={() => setModalState(prev => ({ ...prev, generationModalOpen: true }))}
            onRegenerate={() => setModalState(prev => ({ ...prev, generationModalOpen: true }))}
            onClearFilters={handleClearAllFilters}
            enableDragDrop={true}
            onSessionSwap={handleSessionSwap}
            onSessionMove={handleSessionMove}
            timetableStatus={currentStatus === TimetableStatus.PUBLISHED ? 'published' : 'draft'}
          />

          {/* ═══════════════ PROMINENT PUBLISH CTA ═══════════════ */}
          {hasDraft && currentStatus === TimetableStatus.DRAFT && sessions.length > 0 && (
            <div className="relative">
              <Card className="border-2 border-emerald-200 bg-gradient-to-l from-emerald-50 via-teal-50 to-cyan-50 shadow-lg overflow-hidden">
                <CardContent className="p-8">
                  <div className="flex flex-col items-center text-center">
                    <div className="flex items-center gap-4 mb-4">
                      <HakimCharacter state="success" size="lg" showMessage={false} />
                      <div className="relative bg-white rounded-2xl px-5 py-3 shadow-md border border-emerald-200 max-w-sm">
                        <div className="absolute -right-2 top-4 w-4 h-4 bg-white border-r border-b border-emerald-200 rotate-45" />
                        <p className="text-sm text-emerald-800 font-semibold leading-relaxed">
                          الجدول جاهز! اضغط على زر النشر ليصبح متاحاً لجميع المعلمين والطلاب
                        </p>
                      </div>
                    </div>

                    <Button
                      onClick={() => setModalState(prev => ({ ...prev, publishModalOpen: true }))}
                      className="bg-gradient-to-l from-emerald-600 via-teal-600 to-cyan-600 hover:from-emerald-700 hover:via-teal-700 hover:to-cyan-700
                        text-white shadow-xl hover:shadow-2xl transition-all duration-300 px-10 py-4 text-lg font-bold gap-3 h-auto
                        rounded-2xl transform hover:scale-[1.03] active:scale-[0.98]"
                    >
                      <Send className="h-6 w-6" />
                      نشر الجدول المدرسي
                    </Button>
                    <p className="text-emerald-600 text-xs mt-3">سيتم إتاحة الجدول لجميع المستخدمين بعد النشر</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ═══════════════ INSIGHTS (FULL WIDTH) ═══════════════ */}
          <TimetableInsightsPanel
            insights={insights}
            loading={pageStatus === 'loading'}
          />

          {/* ═══════════════ PREVIOUS TIMETABLES ═══════════════ */}
          <div className="mt-2">
            <button
              onClick={() => {
                if (!showPreviousTimetables) fetchPreviousTimetables();
                setShowPreviousTimetables(prev => !prev);
              }}
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors px-1 py-2 group"
            >
              <Archive className="h-4 w-4" />
              <span>الجداول السابقة</span>
              <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${showPreviousTimetables ? 'rotate-180' : ''}`} />
            </button>

            {showPreviousTimetables && (
              <Card className="border border-gray-200 bg-gray-50/50 mt-2">
                <CardContent className="p-4">
                  {previousTimetables.length === 0 ? (
                    <p className="text-sm text-gray-400 text-center py-6">لا توجد جداول سابقة مؤرشفة</p>
                  ) : (
                    <div className="space-y-3">
                      {previousTimetables.map((tt, idx) => (
                        <div
                          key={tt.id}
                          className="bg-white rounded-xl border border-gray-100 hover:border-violet-200 hover:shadow-sm transition-all overflow-hidden"
                        >
                          <div className="p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-start gap-3 flex-1 min-w-0">
                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-gray-100 to-gray-50 flex items-center justify-center flex-shrink-0 border border-gray-100">
                                  <Hash className="h-4 w-4 text-gray-400" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <p className="text-sm font-semibold text-gray-800 truncate">{tt.version_name}</p>
                                    <Badge variant="outline" className="text-gray-400 border-gray-200 text-[10px] px-1.5 py-0 flex-shrink-0">
                                      مؤرشف
                                    </Badge>
                                  </div>
                                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400 mt-1.5">
                                    {tt.published_at && (
                                      <span className="flex items-center gap-1">
                                        <Calendar className="h-3 w-3" />
                                        {new Date(tt.published_at).toLocaleDateString('ar-SA', { year: 'numeric', month: 'short', day: 'numeric' })}
                                        {' '}
                                        {new Date(tt.published_at).toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' })}
                                      </span>
                                    )}
                                    {tt.published_by_name && (
                                      <span className="flex items-center gap-1">
                                        <User className="h-3 w-3" />
                                        {tt.published_by_name}
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400 mt-1">
                                    {tt.academic_year && (
                                      <span>{tt.academic_year}</span>
                                    )}
                                    {tt.academic_term && (
                                      <span>- {tt.academic_term}</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <Button
                                variant="outline"
                                size="sm"
                                className="flex-shrink-0 text-xs gap-1.5 border-violet-200 text-violet-600 hover:bg-violet-50"
                                disabled={viewingPreviousLoading}
                                onClick={() => viewPreviousTimetable(tt.id)}
                              >
                                <Eye className="h-3.5 w-3.5" />
                                عرض
                              </Button>
                            </div>
                            {(tt.sessions_count > 0 || tt.classes_count > 0) && (
                              <div className="flex items-center gap-4 mt-3 pt-3 border-t border-gray-50">
                                {tt.sessions_count > 0 && (
                                  <span className="text-xs text-gray-400 flex items-center gap-1">
                                    <BookOpen className="h-3 w-3" /> {tt.sessions_count} حصة
                                  </span>
                                )}
                                {tt.classes_count > 0 && (
                                  <span className="text-xs text-gray-400 flex items-center gap-1">
                                    <GraduationCap className="h-3 w-3" /> {tt.classes_count} فصل
                                  </span>
                                )}
                                {tt.teachers_count > 0 && (
                                  <span className="text-xs text-gray-400 flex items-center gap-1">
                                    <Users className="h-3 w-3" /> {tt.teachers_count} معلم
                                  </span>
                                )}
                                {tt.coverage_percent > 0 && (
                                  <span className="text-xs text-gray-400">
                                    تغطية {tt.coverage_percent}%
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* ═══════════════ VIEW PREVIOUS TIMETABLE MODAL ═══════════════ */}
          {viewingPreviousTT && (
            <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setViewingPreviousTT(null)}>
              <div className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between px-6 py-4 border-b bg-gradient-to-l from-violet-50 to-white">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-100 to-purple-100 flex items-center justify-center">
                      <Archive className="h-5 w-5 text-violet-600" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-gray-800">{viewingPreviousTT.version_name || 'جدول سابق'}</h2>
                      <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                        {viewingPreviousTT.published_at && (
                          <span>نُشر: {new Date(viewingPreviousTT.published_at).toLocaleDateString('ar-SA', { year: 'numeric', month: 'short', day: 'numeric' })}</span>
                        )}
                        {viewingPreviousTT.published_by_name && (
                          <span>بواسطة: {viewingPreviousTT.published_by_name}</span>
                        )}
                        {viewingPreviousTT.academic_year && (
                          <span>{viewingPreviousTT.academic_year}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <span className="px-2 py-1 bg-violet-50 rounded-lg">{viewingPreviousTT.sessions_count || 0} حصة</span>
                      <span className="px-2 py-1 bg-emerald-50 rounded-lg">{viewingPreviousTT.classes_count || 0} فصل</span>
                      <span className="px-2 py-1 bg-blue-50 rounded-lg">{viewingPreviousTT.teachers_count || 0} معلم</span>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => setViewingPreviousTT(null)}>
                      <X className="h-5 w-5" />
                    </Button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto p-6">
                  <PreviousTimetableGrid data={viewingPreviousTT} />
                </div>
              </div>
            </div>
          )}

        </div>
      </div>

      <AITimetableGenerationModal
        open={modalState.generationModalOpen}
        onClose={() => setModalState(prev => ({ ...prev, generationModalOpen: false }))}
        onConfirm={handleGenerateTimetable}
        submitting={modalSubmitting}
        readinessSummary={readinessSummary}
        generationInputSummary={{
          totalClasses: classes.length,
          totalTeachers: teachers.length,
          totalSubjects: subjects.length || summary?.subjects_count || 0,
          totalTeachingSlots: teachingSlots.length * workingDays.length
        }}
      />
      <PublishTimetableVersionModal
        open={modalState.publishModalOpen}
        onClose={() => { setModalState(prev => ({ ...prev, publishModalOpen: false })); setConflictCells([]); }}
        onConfirm={handlePublishVersion}
        submitting={modalSubmitting}
        apiCall={api}
        onGapsFilled={() => {
          if (activeVersion?.id) {
            fetchGrid(activeVersion.id, { classId: selectedClassId, teacherId: selectedTeacherId, subjectId: selectedSubjectId, day: selectedDayKey });
            fetchInsights(activeVersion.id);
          }
        }}
        onNavigateToConflict={(conflict) => {
          setConflictCells(prev => {
            const exists = prev.some(c => c.day === conflict.day && c.period === conflict.period);
            if (!exists) return [...prev, { day: conflict.day, period: conflict.period }];
            return prev;
          });
          setTimeout(() => {
            const cellEl = document.getElementById(`cell-${conflict.day}-${conflict.period}`);
            if (cellEl) {
              cellEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
              cellEl.classList.add('animate-pulse');
              setTimeout(() => cellEl.classList.remove('animate-pulse'), 3000);
            }
          }, 300);
        }}
        version={activeVersion ? {
          id: activeVersion.id,
          versionName: activeVersion.version_name || `نسخة ${activeVersion.id?.substring(0, 6)}`,
          qualityScore: activeVersion.quality_score || 0,
          warningsCount: activeVersion.warnings_count || 0,
        } : null}
      />
      <TimetableSessionDetailsDrawer
        open={modalState.sessionDetailsOpen}
        onClose={() => setModalState(prev => ({ ...prev, sessionDetailsOpen: false }))}
        session={selectedSession}
      />
      <TimetableGenerationJourney
        isVisible={showGenerationJourney}
        status={generationStatus}
        errorMessage={journeyErrorMessage}
        onRetry={handleJourneyRetry}
        onClose={handleJourneyClose}
        apiCompleted={journeyApiCompleted}
        apiFailed={journeyApiFailed}
      />
      {showSuccessOverlay && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
          {genConfetti.map((c, i) => (
            <div
              key={`cg-${i}`}
              className="fixed pointer-events-none"
              style={{
                left: c.left, top: '-20px', width: `${c.w}px`, height: `${c.h}px`,
                backgroundColor: c.color, borderRadius: c.radius,
                animation: `celebConfetti ${c.dur}s ease-in forwards`,
                animationDelay: `${c.delay}s`,
                '--end-rot': `${c.endRot}deg`,
              }}
            />
          ))}

          <div className="relative bg-white rounded-3xl shadow-2xl p-10 max-w-lg w-full mx-4 text-center animate-in zoom-in-95 duration-500 overflow-visible">
            <div className="absolute -top-1 -left-1 -right-1 -bottom-1 rounded-3xl bg-gradient-to-br from-violet-400 via-purple-400 to-indigo-400 -z-10 blur-sm opacity-60" />

            <div className="flex justify-center mb-5">
              <div className="relative" style={{ animation: 'celebCircleBounce 2.5s ease-in-out infinite' }}>
                <div className="absolute -inset-8 rounded-full bg-gradient-to-br from-violet-400/30 to-cyan-400/20 blur-2xl" style={{ animation: 'celebGlow 2s ease-in-out infinite alternate' }} />
                <div className="relative w-40 h-40 rounded-full overflow-hidden border-4 border-violet-300/60 shadow-2xl shadow-violet-500/30 bg-gradient-to-br from-violet-50 via-purple-50 to-cyan-50 p-2.5">
                  <img src="/hakim-poses/congratulating-student.png" alt="حكيم" className="hakim-img w-full h-full object-contain drop-shadow-xl" />
                </div>
                <div className="absolute -top-3 -right-2 w-11 h-11 rounded-full bg-yellow-400 flex items-center justify-center shadow-lg text-xl" style={{ animation: 'celebEmoji 1.5s ease-in-out infinite' }}>🎉</div>
                <div className="absolute top-6 -left-5 w-9 h-9 rounded-full bg-violet-300 flex items-center justify-center shadow-lg text-lg" style={{ animation: 'celebEmoji 1.5s ease-in-out infinite 0.3s' }}>✨</div>
                <div className="absolute -bottom-2 -right-3 w-9 h-9 rounded-full bg-cyan-300 flex items-center justify-center shadow-lg text-lg" style={{ animation: 'celebEmoji 1.5s ease-in-out infinite 0.6s' }}>⭐</div>
                <div className="absolute -bottom-1 -left-2 w-9 h-9 rounded-full bg-emerald-300 flex items-center justify-center shadow-lg text-lg" style={{ animation: 'celebEmoji 1.5s ease-in-out infinite 0.9s' }}>🏆</div>
              </div>
            </div>

            <h2 className="text-2xl font-bold font-cairo text-gray-900 mb-2">
              تم إنشاء الجدول الدراسي بنجاح!
            </h2>
            <p className="text-gray-500 font-tajawal text-base mb-5">
              {successSessionsCount > 0 && <span className="block text-emerald-600 font-bold text-lg mb-1">{successSessionsCount} حصة دراسية</span>}
            </p>

            <div className="bg-gradient-to-l from-violet-50 to-purple-50 rounded-2xl px-5 py-4 border border-violet-100">
              <div className="relative bg-white rounded-xl px-5 py-3 shadow-sm border border-violet-200">
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-8 h-8 rounded-lg overflow-hidden bg-violet-100 p-0.5 flex-shrink-0">
                    <img src="/hakim-poses/positive-feedback.png" alt="حكيم" className="hakim-img w-full h-full object-contain" />
                  </div>
                  <span className="text-xs font-cairo font-bold text-violet-700">حكيم يقول:</span>
                </div>
                <p className="text-sm text-violet-800 font-tajawal font-medium leading-relaxed">
                  رائع! تم إنشاء الجدول بنجاح. يمكنك الآن مراجعته أو نشره للمدرسة.
                </p>
              </div>
            </div>

            <div className="mt-5 flex justify-center">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="w-2 h-2 rounded-full bg-emerald-300 animate-pulse" style={{ animationDelay: '0.2s' }} />
                <span className="w-2 h-2 rounded-full bg-emerald-200 animate-pulse" style={{ animationDelay: '0.4s' }} />
                <span className="text-xs text-gray-400 font-tajawal ms-2">جاري الانتقال للمراجعة...</span>
              </div>
            </div>
          </div>
        </div>
      )}
      {showPublishSuccessOverlay && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
          {pubConfetti.map((c, i) => (
            <div
              key={`cp-${i}`}
              className="fixed pointer-events-none"
              style={{
                left: c.left, top: '-20px', width: `${c.w}px`, height: `${c.h}px`,
                backgroundColor: c.color, borderRadius: c.radius,
                animation: `celebConfetti ${c.dur}s ease-in forwards`,
                animationDelay: `${c.delay}s`,
                '--end-rot': `${c.endRot}deg`,
              }}
            />
          ))}

          <div className="relative bg-white rounded-3xl shadow-2xl p-10 max-w-lg w-full mx-4 text-center animate-in zoom-in-95 duration-500 overflow-visible">
            <div className="absolute -top-1 -left-1 -right-1 -bottom-1 rounded-3xl bg-gradient-to-br from-emerald-400 via-teal-400 to-cyan-400 -z-10 blur-sm opacity-60" />

            <div className="flex justify-center mb-5">
              <div className="relative" style={{ animation: 'celebCircleBounce 2.5s ease-in-out infinite' }}>
                <div className="absolute -inset-8 rounded-full bg-gradient-to-br from-emerald-400/30 to-cyan-400/20 blur-2xl" style={{ animation: 'celebGlow 2s ease-in-out infinite alternate' }} />
                <div className="relative w-40 h-40 rounded-full overflow-hidden border-4 border-emerald-300/60 shadow-2xl shadow-emerald-500/30 bg-gradient-to-br from-emerald-50 via-teal-50 to-cyan-50 p-2.5">
                  <img src="/hakim-poses/congratulating-student.png" alt="حكيم" className="hakim-img w-full h-full object-contain drop-shadow-xl" />
                </div>
                <div className="absolute -top-3 -right-2 w-11 h-11 rounded-full bg-yellow-400 flex items-center justify-center shadow-lg text-xl" style={{ animation: 'celebEmoji 1.5s ease-in-out infinite' }}>✅</div>
                <div className="absolute top-6 -left-5 w-9 h-9 rounded-full bg-emerald-400 flex items-center justify-center shadow-lg text-lg" style={{ animation: 'celebEmoji 1.5s ease-in-out infinite 0.3s' }}>🎉</div>
                <div className="absolute -bottom-2 -right-3 w-9 h-9 rounded-full bg-cyan-300 flex items-center justify-center shadow-lg text-lg" style={{ animation: 'celebEmoji 1.5s ease-in-out infinite 0.6s' }}>⭐</div>
                <div className="absolute -bottom-1 -left-2 w-9 h-9 rounded-full bg-violet-300 flex items-center justify-center shadow-lg text-lg" style={{ animation: 'celebEmoji 1.5s ease-in-out infinite 0.9s' }}>🏆</div>
              </div>
            </div>

            <h2 className="text-2xl font-bold font-cairo text-gray-900 mb-2">
              تم نشر الجدول بنجاح!
            </h2>
            <p className="text-gray-600 font-tajawal text-base mb-5">
              <span className="block text-emerald-600 font-bold text-lg mb-1">أصبح هو الجدول الرسمي المعتمد</span>
              الجدول منشور ومتاح الآن لجميع المعلمين والطلاب
            </p>

            <div className="bg-gradient-to-l from-emerald-50 to-teal-50 rounded-2xl px-5 py-4 border border-emerald-100">
              <div className="relative bg-white rounded-xl px-5 py-3 shadow-sm border border-emerald-200">
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-8 h-8 rounded-lg overflow-hidden bg-emerald-100 p-0.5 flex-shrink-0">
                    <img src="/hakim-poses/positive-feedback.png" alt="حكيم" className="hakim-img w-full h-full object-contain" />
                  </div>
                  <span className="text-xs font-cairo font-bold text-emerald-700">حكيم يقول:</span>
                </div>
                <p className="text-sm text-emerald-800 font-tajawal font-medium leading-relaxed">
                  ممتاز! الجدول الآن نشط ومعتمد رسمياً. جميع المعلمين يمكنهم الاطلاع عليه الآن.
                </p>
              </div>
            </div>

            <div className="mt-5 flex justify-center">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                <span className="text-sm text-emerald-600 font-tajawal font-medium">الجدول المعتمد</span>
              </div>
            </div>
          </div>
        </div>
      )}
      <style>{`
        @keyframes celebCircleBounce {
          0%, 100% { transform: translateY(0) scale(1); }
          15% { transform: translateY(-18px) scale(1.05); }
          30% { transform: translateY(-4px) scale(0.98); }
          45% { transform: translateY(-14px) scale(1.03); }
          60% { transform: translateY(-2px) scale(0.99); }
          75% { transform: translateY(-10px) scale(1.02); }
          90% { transform: translateY(-1px) scale(1); }
        }
        @keyframes celebGlow {
          0% { opacity: 0.3; transform: scale(0.95); }
          100% { opacity: 0.7; transform: scale(1.15); }
        }
        @keyframes celebEmoji {
          0%, 100% { transform: scale(1) translateY(0); }
          50% { transform: scale(1.25) translateY(-10px); }
        }
        @keyframes celebConfetti {
          0% { transform: translateY(0) rotate(0deg) scale(1); opacity: 1; }
          50% { opacity: 1; }
          100% { transform: translateY(100vh) rotate(var(--end-rot, 720deg)) scale(0.5); opacity: 0; }
        }
      `}</style>
      <style>{`
        @media print {
          .print\\:hidden, [data-testid="sidebar"], nav, header, .sidebar { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          main { margin: 0 !important; padding: 0 !important; }
          .rounded-2xl { border-radius: 0 !important; }
          table { page-break-inside: auto; }
          tr { page-break-inside: avoid; }
        }
      `}</style>
    </Sidebar>
  );
};

export default PrincipalTimetablePage;
