import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Progress } from '../../components/ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { formatHijriDate } from '../../utils/hijriDate';
import { Textarea } from '../../components/ui/textarea';
import { DialogFooter } from '../../components/ui/dialog';
import {
  Users, Search, Loader2, RefreshCw, Eye, GraduationCap,
  Phone, Mail, ClipboardCheck, FileText, TrendingUp, Star,
  BookOpen, Calendar, ChevronLeft, BarChart3, Brain, Target,
  CheckCircle, AlertTriangle, Sparkles, ArrowUpCircle, ArrowDownCircle,
  Lightbulb, Activity, MessageSquare, Send, Plus, UserPlus, Link2, Upload,
  Pencil, Trash2
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';
import AddStudentWizard from '../../components/wizards/AddStudentWizard';

// Phase 1 IT — server-side cap (#192 spec §5.6).
const WORKSPACE_STUDENTS_MAX = 200;

// Spec §5.6 — canonical parent-contact ownership. Read precedence:
// linked parent fields when `parent_id` is set, otherwise the inline
// `pending_parent_*` strings captured at student-create time.
function getStudentParentDisplay(student) {
  if (!student) return { name: '', phone: '', email: '', isLinked: false };
  if (student.parent_id) {
    return {
      name: student.parent_name || '',
      phone: student.parent_phone || '',
      email: student.parent_email || '',
      isLinked: true,
    };
  }
  return {
    name: student.pending_parent_name || '',
    phone: student.pending_parent_phone || '',
    email: student.pending_parent_email || '',
    isLinked: false,
  };
}

import { useTranslation } from '../../contexts/ThemeContext';
import { ResponsiveTable } from '../../components/ui/ResponsiveTable';

// 2026-05-19 — Headless `TeacherStudentsPanel` wrapper. Mirrors the
// `TeacherSubjectsPanel` / `BulkImportPanel` / `WorkspaceSchedulePanel`
// pattern so the same student-directory surface can be embedded as a
// sub-tab inside فصولي (TeacherClassesPage) without rendering a nested
// `<Sidebar>` shell or a second page-level header. `embedded` collapses
// the page chrome; default-false preserves the standalone /teacher/students
// route exactly.
export function TeacherStudentsPanel(props) {
  return <TeacherStudentsPage embedded {...props} />;
}

export default function TeacherStudentsPage({ embedded = false } = {}) {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const isIndependentTeacher = user?.role === 'independent_teacher';
  const [showAddStudent, setShowAddStudent] = useState(false);
  const [workspaceStudentCount, setWorkspaceStudentCount] = useState(null);
  const [workspaceGrades, setWorkspaceGrades] = useState([]);
  const [workspaceClasses, setWorkspaceClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  // 2026-05-19 — IT-only: default to the workspace-wide pool ("الكل")
  // so newly-imported students with `class_id = null` are visible
  // immediately in the IT "طلابي" tab. Sentinel values:
  //   'all'        → every workspace student
  //   'unassigned' → only rows with `class_id` null/empty
  //   <classId>    → the legacy class-scoped path
  // Regular `teacher` callers (school tenants) keep the legacy
  // empty-default + auto-select-first-class behavior. Switching them
  // to `/students` would widen their view beyond assigned classes,
  // because `/classes/{id}/students` does the per-teacher object-
  // level check via `can_view_class` while `/students` only enforces
  // tenant scope. Gate strictly on `isIndependentTeacher`.
  const [selectedClass, setSelectedClass] = useState(
    isIndependentTeacher ? 'all' : ''
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);
  const [studentDetails, setStudentDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [aiInsights, setAiInsights] = useState(null);
  const [loadingAI, setLoadingAI] = useState(false);
  const [showMessageDialog, setShowMessageDialog] = useState(false);
  const [messageTarget, setMessageTarget] = useState(null);
  const [messageSubject, setMessageSubject] = useState('');
  const [messageBody, setMessageBody] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);

  // Invite-Parent dialog state (#199 spec §5.6 — atomic Pending → Linked).
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteTarget, setInviteTarget] = useState(null);
  const [inviteForm, setInviteForm] = useState({
    full_name: '', phone: '', email: '', national_id: '', relationship: 'guardian',
  });
  const [inviteSubmitting, setInviteSubmitting] = useState(false);

  // Task #206 — IT §6.2c parent-invitation status chip.
  // Maps `student.id → { id, status, expires_at, sent_at, accepted_at }`
  // (or `null` when no invitation exists). Populated lazily after the
  // student list loads so a class with no IT students still renders.
  const [invitationByStudent, setInvitationByStudent] = useState({});
  // Task #251 — deep-link via /teacher/students?student_id=… opened from
  // the IT command palette. Tracks whether we've already auto-opened the
  // details dialog so we don't reopen on every render.
  const _location = useLocation();
  const _navigate = useNavigate();
  const _deepLinkOpenedRef = useRef(null);

  const { nassaqError, nassaqWarning, nassaqInfo, nassaqConfirm } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;

  // Workspace count + dropdown options for the IT inline-create wizard
  // (#192 spec §5.6). Read-only, mirrors the chip pattern from
  // TeacherClassesPage. Authoritative cap is enforced server-side via
  // the 409 from `enforce_student_quota`.
  const fetchWorkspaceStudentCount = useCallback(async () => {
    if (!isIndependentTeacher) return;
    try {
      const res = await api.get('/students');
      const list = Array.isArray(res.data) ? res.data : (res.data?.students || []);
      setWorkspaceStudentCount(list.length);
    } catch (_e) {
      // Soft-fail — chip falls back to the locally-known students.length.
    }
  }, [api, isIndependentTeacher]);

  const fetchWorkspaceWizardOptions = useCallback(async () => {
    if (!isIndependentTeacher) return;
    try {
      const [gradesRes, classesRes] = await Promise.all([
        api.get('/grade-levels').catch(() => ({ data: [] })),
        api.get('/classes').catch(() => ({ data: [] })),
      ]);
      const grades = Array.isArray(gradesRes.data) ? gradesRes.data : (gradesRes.data?.items || []);
      const cls = Array.isArray(classesRes.data) ? classesRes.data : (classesRes.data?.items || []);
      setWorkspaceGrades(grades);
      setWorkspaceClasses(cls);
    } catch (_e) {
      // Wizard handles empty arrays gracefully.
    }
  }, [api, isIndependentTeacher]);

  useEffect(() => {
    if (isIndependentTeacher) {
      fetchWorkspaceStudentCount();
      fetchWorkspaceWizardOptions();
    }
  }, [isIndependentTeacher, fetchWorkspaceStudentCount, fetchWorkspaceWizardOptions]);

  const handleOpenAddStudent = useCallback(() => {
    if (workspaceStudentCount != null && workspaceStudentCount >= WORKSPACE_STUDENTS_MAX) {
      nassaqWarning(
        isRTL
          ? `بلغت الحد الأقصى للطلاب في مساحة عملك (${WORKSPACE_STUDENTS_MAX}). لا يمكن إضافة المزيد.`
          : `You have reached your workspace student limit (${WORKSPACE_STUDENTS_MAX}). Cannot add more.`
      );
      return;
    }
    setShowAddStudent(true);
  }, [workspaceStudentCount, nassaqWarning, isRTL]);

  const fetchClasses = useCallback(async () => {
    if (!teacherId) return;
    
    setLoading(true);
    try {
      const classesRes = await api.get(`/teacher/classes/${teacherId}`).catch(() => ({ data: [] }));
      setClasses(classesRes.data || []);
      // 2026-05-19 — Auto-select-first-class is preserved for non-IT
      // teachers (school tenants), who must stay on the class-scoped
      // `/classes/{id}/students` path. IT workspaces skip this so the
      // 'all' default (workspace pool) sticks and unassigned imported
      // students remain visible.
      if (
        !isIndependentTeacher
        && classesRes.data?.length > 0
        && !selectedClass
      ) {
        setSelectedClass(classesRes.data[0].id);
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, isIndependentTeacher, selectedClass]);

  const fetchStudents = useCallback(async () => {
    // 2026-05-19 — Non-IT teachers must stay on the class-scoped
    // path; without a concrete class selected, render nothing rather
    // than calling `/students` (which is tenant-scoped but not
    // class-assignment-scoped and would widen their view).
    if (!selectedClass) {
      setStudents([]);
      return;
    }
    setLoading(true);
    try {
      // 2026-05-19 — Three filter modes (IT-only pool routes; non-IT
      // never reaches `isPool` because the sentinel values are not
      // selectable for them and the early return above guards `''`):
      //   'all'        → GET /students (workspace pool, includes
      //                  unassigned rows; backend returns `class_name`).
      //   'unassigned' → GET /students then client-side filter on
      //                  `class_id` null/empty so the IT teacher can
      //                  isolate the newly-imported batch and assign
      //                  them to a class.
      //   <classId>    → GET /classes/{id}/students (existing path,
      //                  keeps per-class stats endpoint usable).
      // Stats endpoint is class-scoped so we only call it for a
      // concrete class; pool views render the raw rows.
      const isPool =
        isIndependentTeacher
        && (selectedClass === 'all' || selectedClass === 'unassigned');
      let rawStudents = [];
      let statsMap = {};

      if (isPool) {
        const studentsRes = await api.get('/students');
        rawStudents = Array.isArray(studentsRes.data) ? studentsRes.data : [];
        if (selectedClass === 'unassigned') {
          rawStudents = rawStudents.filter((s) => !s.class_id);
        }
      } else {
        const [studentsRes, statsRes] = await Promise.all([
          api.get(`/classes/${selectedClass}/students`),
          api.get(`/classes/${selectedClass}/student-stats`).catch(() => ({ data: {} })),
        ]);
        rawStudents = Array.isArray(studentsRes.data) ? studentsRes.data : [];
        statsMap = statsRes.data || {};
      }

      const enrichedStudents = rawStudents.map((student) => {
        const s = statsMap[student.id] || {};
        return {
          ...student,
          attendance_rate: s.attendance_rate ?? student.attendance_rate ?? 0,
          average_grade: s.average_grade ?? student.average_grade ?? 0,
          behavior_points: s.behavior_points ?? student.behavior_points ?? 0,
        };
      });

      setStudents(enrichedStudents);
    } catch (error) {
      console.error('Error:', error);
      nassaqError(t('errorLoadingStudents'));
    } finally {
      setLoading(false);
    }
  }, [api, selectedClass, isIndependentTeacher, nassaqError, t]);

  useEffect(() => {
    fetchClasses();
  }, [fetchClasses]);

  useEffect(() => {
    // 2026-05-19 — fetchStudents handles the "no class selected" case
    // internally (clears the list for non-IT, fetches pool for IT).
    fetchStudents();
  }, [selectedClass, fetchStudents]);

  // Task #206 — fetch the latest parent-invitation row for every
  // IT-workspace student so the chip renders alongside the Invite-
  // Parent / Message-Parent CTA. We deliberately fetch for linked
  // students too: once a parent accepts, `student.parent_id` is set
  // and the chip transitions to the `accepted` state (with the
  // tooltip carrying `accepted_at` + `parent_name`) — gating on
  // `!parent_id` would hide that state entirely.
  const refreshInvitationsForStudents = useCallback(async (studentList) => {
    if (!isIndependentTeacher || !studentList?.length) return;
    const candidates = studentList;
    if (!candidates.length) return;
    const results = await Promise.all(candidates.map(async (s) => {
      try {
        const res = await api.get(
          `/independent-teacher/students/${s.id}/parent-invitation`,
        );
        return [s.id, res?.data?.invitation || null];
      } catch (_e) {
        return [s.id, null];
      }
    }));
    setInvitationByStudent((prev) => {
      const next = { ...prev };
      for (const [sid, inv] of results) next[sid] = inv;
      return next;
    });
  }, [api, isIndependentTeacher]);

  useEffect(() => {
    if (isIndependentTeacher && students.length) {
      refreshInvitationsForStudents(students);
    }
  }, [isIndependentTeacher, students, refreshInvitationsForStudents]);

  const cancelInvitationForStudent = useCallback(async (student) => {
    const inv = invitationByStudent[student.id];
    if (!inv?.id) return;
    nassaqConfirm(
      isRTL
        ? (t('cancelInvitationConfirm') || 'هل تريد إلغاء دعوة ولي الأمر؟ سيتعذّر استخدام الرابط بعد ذلك.')
        : (t('cancelInvitationConfirm') || 'Cancel this parent invitation? The link will stop working.'),
      async () => {
        try {
          await api.post(
            `/independent-teacher/parent-invitations/${inv.id}/cancel`,
          );
          nassaqInfo(t('invitationCancelled') || (isRTL ? 'تم إلغاء الدعوة بنجاح.' : 'Invitation cancelled.'));
          await refreshInvitationsForStudents([student]);
        } catch (err) {
          const status = err?.response?.status;
          const detail = err?.response?.data?.detail;
          // §5.7 step-up envelope is replayed by the global axios
          // interceptor — only surface other errors.
          const stepUpCodes = new Set([
            'MFA_STEPUP_REQUIRED', 'MFA_PASSKEY_REQUIRED', 'MFA_RESTORE_REQUIRED',
          ]);
          const isStepUp = (status === 401 || status === 403)
            && (typeof detail === 'object' && stepUpCodes.has(detail?.code));
          if (!isStepUp) {
            nassaqError(t('invitationCancelFailed')
              || (isRTL ? 'تعذّر إلغاء الدعوة — حاول لاحقًا.' : 'Could not cancel the invitation. Please try again.'));
          }
        }
      },
      {
        title: t('invitationConfirmCancelTitle') || (isRTL ? 'تأكيد الإلغاء' : 'Confirm cancellation'),
        confirmText: t('cancelInvitation') || (isRTL ? 'إلغاء الدعوة' : 'Cancel invitation'),
        cancelText: t('back') || (isRTL ? 'تراجع' : 'Back'),
        type: 'warning',
      },
    );
  }, [api, invitationByStudent, isRTL, nassaqConfirm, nassaqError, nassaqInfo, refreshInvitationsForStudents, t]);

  const handleAddStudentSuccess = useCallback(() => {
    fetchWorkspaceStudentCount();
    fetchStudents();
  }, [fetchWorkspaceStudentCount, fetchStudents]);

  const fetchAIInsights = async (studentId) => {
    setLoadingAI(true);
    try {
      const res = await api.get(`/hakim/student/${studentId}/improvement-plan?days=30`);
      setAiInsights(res.data);
    } catch (e) {
      console.error('Error fetching AI insights:', e);
      setAiInsights(null);
    } finally {
      setLoadingAI(false);
    }
  };

  // Task #251 — auto-open details dialog when arriving with
  // ?student_id=… (deep-link from the IT command palette).
  useEffect(() => {
    if (!students || !students.length) return;
    const params = new URLSearchParams(_location.search);
    const sid = params.get('student_id');
    if (!sid || _deepLinkOpenedRef.current === sid) return;
    const match = students.find((s) => s.id === sid);
    if (!match) return;
    _deepLinkOpenedRef.current = sid;
    // eslint-disable-next-line no-use-before-define
    viewStudentDetails(match);
    // Strip the deep-link param so a refresh doesn't replay the dialog.
    params.delete('student_id');
    _navigate(
      { pathname: _location.pathname, search: params.toString() ? `?${params.toString()}` : '' },
      { replace: true },
    );
  }, [students, _location.pathname, _location.search, _navigate]);

  const viewStudentDetails = async (student) => {
    setSelectedStudent(student);
    setShowDetailsDialog(true);
    setLoadingDetails(true);
    setAiInsights(null);
    
    try {
      const analyticsRes = await api.get(`/students/${student.id}/analytics`).catch(() => ({ data: null }));
      setStudentDetails(analyticsRes.data || {
        attendance: { rate: 0, total: 0, present: 0, absent: 0, late: 0, trend: [], recent: [] },
        grades: { average: 0, count: 0, records: [] },
        participation: { total_interactions: 0, participation_count: 0, recent: [] },
        behavior: { total_points: 0, records: [], session_records: [] },
        skills: []
      });
      fetchAIInsights(student.id);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoadingDetails(false);
    }
  };

  const openMessageParent = (e, student) => {
    e.stopPropagation();
    if (!student.parent_id) {
      nassaqError(t('noParentLinkedToThisStudent'));
      return;
    }
    setMessageTarget(student);
    setMessageSubject('');
    setMessageBody('');
    setShowMessageDialog(true);
  };

  const handleSendParentMessage = async () => {
    if (!messageSubject.trim() || !messageBody.trim()) {
      nassaqError(t('pleaseFillInSubjectAndMessage'));
      return;
    }
    setSendingMessage(true);
    try {
      await api.post('/messages', {
        sender_id: teacherId,
        sender_type: 'teacher',
        recipient_ids: [messageTarget.parent_id],
        type: 'follow_up',
        subject: messageSubject.trim(),
        body: messageBody.trim(),
        student_id: messageTarget.id,
        student_name: messageTarget.full_name,
        class_id: selectedClass
      });
      toast.success(t('messageSentToParentSuccessfully'));
      setShowMessageDialog(false);
    } catch (error) {
      nassaqError(t('errorSendingMessage'));
    } finally {
      setSendingMessage(false);
    }
  };

  const openInviteParent = (e, student) => {
    e.stopPropagation();
    setInviteTarget(student);
    setInviteForm({
      full_name: student.pending_parent_name || '',
      phone: student.pending_parent_phone || '',
      email: student.pending_parent_email || '',
      national_id: '',
      relationship: 'guardian',
    });
    setInviteOpen(true);
  };

  const handleInviteParent = async () => {
    if (!inviteTarget) return;
    const f = inviteForm;
    if (!f.phone?.trim() && !f.email?.trim() && !f.national_id?.trim()) {
      nassaqError(isRTL
        ? 'يلزم إدخال رقم الجوال أو البريد الإلكتروني أو رقم الهوية'
        : 'Phone, email, or national ID is required');
      return;
    }
    setInviteSubmitting(true);
    try {
      const body = {
        full_name: f.full_name?.trim() || null,
        phone: f.phone?.trim() || null,
        email: f.email?.trim() || null,
        national_id: f.national_id?.trim() || null,
        relationship: f.relationship || 'guardian',
      };
      const res = await api.post(
        `/independent-teacher/students/${inviteTarget.id}/invite-parent`,
        body,
      );
      const matched = res.data?.matched_by;
      const matchedAr = matched === 'new'
        ? 'تم إنشاء حساب جديد'
        : 'تم الربط بحساب موجود';
      setInviteOpen(false);
      setInviteTarget(null);
      await fetchStudents();
      nassaqInfo(isRTL
        ? `تم ربط ولي الأمر بنجاح — ${matchedAr}`
        : 'Parent linked successfully');
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail
        || err?.response?.data?.error?.message;
      const msg = typeof detail === 'string'
        ? detail
        : (isRTL ? 'تعذّر ربط ولي الأمر — حاول لاحقًا.' : 'Failed to link parent.');
      // 401/403 with MFA_STEPUP_REQUIRED is intercepted globally and
      // replayed by the AuthContext axios interceptor (Task #199 surfaces
      // 403 specifically) — only surface other errors here.
      const stepUpCodes = new Set([
        'MFA_STEPUP_REQUIRED', 'MFA_PASSKEY_REQUIRED', 'MFA_RESTORE_REQUIRED',
      ]);
      const stepUp = (status === 401 || status === 403)
        && (typeof detail === 'object' && stepUpCodes.has(detail?.code));
      if (!stepUp) nassaqError(msg);
    } finally {
      setInviteSubmitting(false);
    }
  };

  const filteredStudents = students.filter(s =>
    s.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.student_id?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // IT student edit/delete dialogs (Task #185).
  const [editStudentDialog, setEditStudentDialog] = useState(null); // { id, full_name, grade, gender }
  const [editStudentSaving, setEditStudentSaving] = useState(false);

  const handleEditStudent = (e, student) => {
    e.stopPropagation();
    setEditStudentDialog({
      id: student.id,
      full_name: student.full_name || '',
      grade: student.grade || '',
      gender: student.gender || '',
      // 2026-05-19 — Carry the current class_id so the new dropdown
      // can pre-select it (or fall back to the 'unassigned' sentinel
      // for freshly imported rows). The sentinel is mapped back to
      // `null` in `saveEditStudent` so the PUT body matches the
      // backend contract.
      class_id: student.class_id || '',
      _original_class_id: student.class_id || null,
    });
  };

  const handleDeleteStudent = (e, student) => {
    e.stopPropagation();
    nassaqConfirm(
      isRTL
        ? `هل تريد حذف الطالب "${student.full_name}" نهائياً؟ سيتم حذف كل بياناته.`
        : `Permanently delete student "${student.full_name}"? All their data will be removed.`,
      async (ok) => {
        if (!ok) return;
        try {
          await api.delete(`/students/${student.id}`);
          await fetchStudents();
          if (typeof fetchWorkspaceStudentCount === 'function') {
            await fetchWorkspaceStudentCount();
          }
          nassaqInfo(isRTL ? 'تم حذف الطالب' : 'Student deleted');
        } catch (err) {
          const detail = err?.response?.data?.detail;
          nassaqError(typeof detail === 'string' ? detail : (isRTL ? 'تعذّر حذف الطالب' : 'Could not delete student'));
        }
      }
    );
  };

  const saveEditStudent = async () => {
    if (!editStudentDialog) return;
    const full_name = (editStudentDialog.full_name || '').trim();
    if (!full_name) {
      nassaqError(isRTL ? 'الاسم مطلوب' : 'Name is required');
      return;
    }
    setEditStudentSaving(true);
    try {
      const body = { full_name };
      if (editStudentDialog.grade) body.grade = editStudentDialog.grade;
      if (editStudentDialog.gender) body.gender = editStudentDialog.gender;
      // 2026-05-19 — Class assignment from the dropdown. The 'unassigned'
      // sentinel maps to `null` (clears the assignment). A real class_id
      // is forwarded as-is; the backend validates it belongs to the
      // teacher's workspace and 404s otherwise. We only send the field
      // when the user actually changed it to avoid touching unrelated
      // assignments on edits that only changed name/grade/gender.
      const nextClassId =
        editStudentDialog.class_id === 'unassigned'
          ? null
          : (editStudentDialog.class_id || null);
      const originalClassId = editStudentDialog._original_class_id ?? null;
      if (nextClassId !== originalClassId) {
        body.class_id = nextClassId;
      }
      await api.put(`/students/${editStudentDialog.id}`, body);
      // 2026-05-19 — Optimistic local update so the row reflects the new
      // class immediately and disappears from the "غير معينين" filter
      // without waiting for the refetch round-trip. fetchStudents() still
      // runs to reconcile with server truth (and to drop a row from the
      // current view if the new class doesn't match the active filter).
      if ('class_id' in body) {
        const newClass = workspaceClasses.find((c) => c.id === nextClassId);
        setStudents((prev) => prev.map((s) =>
          s.id === editStudentDialog.id
            ? { ...s, class_id: nextClassId, class_name: newClass?.name || null }
            : s,
        ));
      }
      setEditStudentDialog(null);
      await fetchStudents();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      nassaqError(typeof detail === 'string' ? detail : (isRTL ? 'تعذّر التحديث' : 'Could not update'));
    } finally {
      setEditStudentSaving(false);
    }
  };

  const getGradeColor = (grade) => {
    if (grade >= 90) return 'text-green-600';
    if (grade >= 75) return 'text-blue-600';
    if (grade >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  // 2026-05-19 — `embedded` mode skips the Sidebar shell, the floating
  // HakimAssistant, and the gradient page-background so the panel can be
  // rendered as a sub-tab inside another page (TeacherClassesPage) without
  // double-rendering the layout chrome. Behavior is otherwise identical.
  const Shell = embedded ? React.Fragment : Sidebar;
  const shellProps = embedded ? {} : undefined;
  const outerClassName = embedded
    ? ''
    : 'min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800';
  const headerClassName = embedded
    ? 'bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4 rounded-md'
    : 'sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4';

  return (
    <Shell {...(shellProps || {})}>
      <div className={outerClassName} dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <div className={headerClassName}>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('myStudents')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('viewAndTrackStudentData')}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {isIndependentTeacher && (
                <>
                  <Badge
                    variant="outline"
                    className="h-9 px-3 font-cairo text-xs flex items-center"
                    data-testid="workspace-students-usage-chip"
                  >
                    {(t('workspaceStudentsUsageChip') || '{0} / {1}')
                      .replace('{0}', workspaceStudentCount ?? students.length)
                      .replace('{1}', WORKSPACE_STUDENTS_MAX)}
                  </Badge>
                  <Button
                    size="sm"
                    className="h-9 gap-1.5 bg-brand-navy hover:bg-brand-navy/90 text-white"
                    onClick={handleOpenAddStudent}
                    data-testid="workspace-add-student-cta"
                  >
                    <Plus className="h-4 w-4" />
                    <span className="hidden sm:inline">{t('addStudent')}</span>
                  </Button>
                  <div className="hidden sm:block h-6 w-px bg-border" />
                </>
              )}
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-full sm:w-[200px]" data-testid="class-select">
                  <SelectValue placeholder={t('selectClass')} />
                </SelectTrigger>
                <SelectContent>
                  {/* 2026-05-19 — Workspace pool + unassigned sentinels
                      are IT-only. Regular teachers must stay on the
                      class-scoped `/classes/{id}/students` path which
                      enforces per-teacher object-level checks; the
                      pool endpoint only enforces tenant scope and
                      would widen their view to every student in the
                      school. */}
                  {isIndependentTeacher && (
                    <>
                      <SelectItem value="all" data-testid="class-filter-all">
                        {isRTL ? 'الكل' : 'All'}
                      </SelectItem>
                      <SelectItem value="unassigned" data-testid="class-filter-unassigned">
                        {isRTL ? 'غير معينين' : 'Unassigned'}
                      </SelectItem>
                    </>
                  )}
                  {classes.map(cls => (
                    <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('search')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="ps-9 w-full sm:w-[180px]"
                />
              </div>
              <Button variant="outline" size="icon" onClick={fetchStudents} disabled={loading}>
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>

        {/* Stats Summary */}
        <div className="p-4 border-b bg-muted/30">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
            <div className="text-center p-3 rounded-lg bg-white dark:bg-gray-800">
              <div className="text-2xl font-bold text-brand-navy">{filteredStudents.length}</div>
              <div className="text-xs text-muted-foreground">{isRTL ? 'طالب' : 'Students'}</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-white dark:bg-gray-800">
              <div className="text-2xl font-bold text-green-600">
                {Math.round(filteredStudents.reduce((s, st) => s + (st.attendance_rate || 0), 0) / filteredStudents.length) || 0}%
              </div>
              <div className="text-xs text-muted-foreground">{t('avgAttendance')}</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-white dark:bg-gray-800">
              <div className="text-2xl font-bold text-blue-600">
                {Math.round(filteredStudents.reduce((s, st) => s + (st.average_grade || 0), 0) / filteredStudents.length) || 0}
              </div>
              <div className="text-xs text-muted-foreground">{t('avgGrade')}</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-white dark:bg-gray-800">
              <div className="text-2xl font-bold text-purple-600">
                {filteredStudents.filter(s => (s.average_grade || 0) >= 90).length}
              </div>
              <div className="text-xs text-muted-foreground">{t('topStudents3')}</div>
            </div>
          </div>
        </div>

        {/* Students Grid */}
        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : filteredStudents.length === 0 ? (
            // Task #287 — IT-focused empty state when the workspace has
            // zero students. Mirrors the §5.8 classes empty state: same
            // workspace-accent tokens, dashed card, primary "Add your
            // first student" CTA + secondary "Import from CSV" CTA.
            // Non-IT teachers and search-narrowed empty results keep
            // the existing neutral copy.
            isIndependentTeacher && (workspaceStudentCount ?? 0) === 0 && !searchQuery ? (
              <Card
                className="border-dashed border-workspace-accent-border bg-workspace-accent-light/30"
                data-testid="teacher-students-empty-state-it"
              >
                <CardContent className="text-center py-16">
                  <Users className="h-16 w-16 mx-auto mb-4 text-workspace-accent" />
                  <h3 className="font-bold text-lg mb-2 font-cairo text-workspace-accent-fg">
                    {t('itEmptyStudentsTitle')}
                  </h3>
                  <p className="text-muted-foreground text-sm font-tajawal mb-5 max-w-md mx-auto">
                    {t('itEmptyStudentsDescription')}
                  </p>
                  <div className="flex items-center justify-center gap-2 flex-wrap">
                    <Button
                      onClick={handleOpenAddStudent}
                      className="bg-workspace-accent hover:bg-workspace-accent-fg text-white rounded-xl gap-2 px-5"
                      data-testid="teacher-students-empty-state-cta"
                    >
                      <Plus className="h-4 w-4" />
                      {t('itEmptyStudentsCta')}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => _navigate('/teacher/classes?tab=import')}
                      className="rounded-xl gap-2 px-5 border-workspace-accent-border text-workspace-accent-fg hover:bg-workspace-accent-light/60"
                      data-testid="teacher-students-empty-state-import-cta"
                    >
                      <Upload className="h-4 w-4" />
                      {t('itEmptyStudentsImportCta')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="text-center py-16">
                  <Users className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                  <h3 className="font-bold mb-2">{t('noStudents')}</h3>
                  {/* 2026-05-19 — Replaced "اختر فصلاً لعرض الطلاب"
                      copy. The pool/unassigned views render even with
                      zero matches, so the message must reflect a
                      genuinely empty result rather than asking the
                      teacher to pick a class. */}
                  <p className="text-muted-foreground">
                    {isRTL
                      ? 'لا يوجد طلاب يطابقون التصفية الحالية.'
                      : 'No students match the current filter.'}
                  </p>
                </CardContent>
              </Card>
            )
          ) : (() => {
            const renderStudentCard = (student, idx) => (
                <Card 
                  className="hover:shadow-lg transition-all cursor-pointer border-2 hover:border-brand-turquoise"
                  onClick={() => viewStudentDetails(student)}
                  data-testid={`student-card-${student.id}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 mb-4">
                      <Avatar className="h-14 w-14">
                        <AvatarImage src={student.avatar_url} />
                        <AvatarFallback className="bg-gradient-to-br from-brand-navy to-brand-turquoise text-white text-lg">
                          {student.full_name?.charAt(0) || (idx + 1)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold truncate">{student.full_name || `طالب ${idx + 1}`}</p>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <p className="text-xs text-muted-foreground">{student.student_id || `#${idx + 1}`}</p>
                          {/* 2026-05-19 — Class badge. Imported students
                              with `class_id = null` get a visually
                              distinct "غير معين" amber badge so the
                              teacher can spot the unassigned batch and
                              use the per-row edit dialog to assign
                              them to a class. */}
                          {student.class_id ? (
                            student.class_name && (
                              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">
                                {student.class_name}
                              </Badge>
                            )
                          ) : (
                            <Badge
                              variant="outline"
                              className="text-[10px] px-1.5 py-0 h-4 border-amber-400 text-amber-700 bg-amber-50 dark:bg-amber-900/20"
                              data-testid={`student-unassigned-${student.id}`}
                            >
                              {isRTL ? 'غير معين' : 'Unassigned'}
                            </Badge>
                          )}
                        </div>
                      </div>
                      <ChevronLeft className="h-5 w-5 text-muted-foreground" />
                    </div>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-3 gap-2 text-center mb-3">
                      <div className="p-2 rounded bg-green-50 dark:bg-green-900/20">
                        <ClipboardCheck className="h-4 w-4 mx-auto mb-1 text-green-600" />
                        <div className="text-sm font-bold text-green-700">{student.attendance_rate || 0}%</div>
                        <div className="text-[10px] text-muted-foreground">{isRTL ? 'حضور' : 'Attend'}</div>
                      </div>
                      <div className="p-2 rounded bg-blue-50 dark:bg-blue-900/20">
                        <FileText className="h-4 w-4 mx-auto mb-1 text-blue-600" />
                        <div className={`text-sm font-bold ${getGradeColor(student.average_grade || 0)}`}>
                          {student.average_grade || 0}
                        </div>
                        <div className="text-[10px] text-muted-foreground">{t('grade4')}</div>
                      </div>
                      <div className="p-2 rounded bg-purple-50 dark:bg-purple-900/20">
                        <Star className="h-4 w-4 mx-auto mb-1 text-purple-600" />
                        <div className="text-sm font-bold text-purple-700">{student.behavior_points || 0}</div>
                        <div className="text-[10px] text-muted-foreground">{isRTL ? 'سلوك' : 'Behav'}</div>
                      </div>
                    </div>

                    {/* Progress Bar */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-muted-foreground">{t('overall')}</span>
                        <span className={`font-medium ${getGradeColor(student.average_grade || 0)}`}>
                          {student.average_grade >= 90 ? (t('excellent')) :
                           student.average_grade >= 75 ? (t('veryGood')) :
                           student.average_grade >= 60 ? (t('good')) : (isRTL ? 'يحتاج تحسين' : 'Needs Improvement')}
                        </span>
                      </div>
                      <Progress value={student.average_grade || 0} className="h-2" />
                    </div>

                    {(() => {
                      const pd = getStudentParentDisplay(student);
                      const hasPending = !pd.isLinked && (pd.name || pd.phone || pd.email);
                      // §6.2c: render the invitation status chip for IT
                      // students whenever an invitation row exists — even
                      // after `parent_id` is set on accept — so the
                      // `accepted` state with tooltip ("Linked to <name>")
                      // is reachable per spec. Falls through to the
                      // existing linked / pending UI underneath.
                      const invForChip = isIndependentTeacher ? invitationByStudent[student.id] : null;
                      const chipStatus = invForChip?.status || null;
                      let chipNode = null;
                      if (chipStatus) {
                        const STATUS_STYLES_TOP = {
                          pending: 'text-amber-700 border-amber-300 bg-amber-50',
                          accepted: 'text-emerald-700 border-emerald-300 bg-emerald-50',
                          expired: 'text-gray-600 border-gray-300 bg-gray-50',
                          cancelled: 'text-gray-600 border-gray-300 bg-gray-50',
                        };
                        const STATUS_LABELS_AR_TOP = {
                          pending: 'دعوة معلّقة', accepted: 'تم القبول',
                          expired: 'انتهت صلاحية الدعوة', cancelled: 'تم إلغاء الدعوة',
                        };
                        const STATUS_LABELS_EN_TOP = {
                          pending: 'Invitation pending', accepted: 'Parent linked',
                          expired: 'Invitation expired', cancelled: 'Invitation cancelled',
                        };
                        const lk = `parentInvitationStatus${chipStatus.charAt(0).toUpperCase()}${chipStatus.slice(1)}`;
                        const lbl = t(lk) || (isRTL ? STATUS_LABELS_AR_TOP[chipStatus] : STATUS_LABELS_EN_TOP[chipStatus]);
                        const locale = isRTL ? 'ar' : 'en';
                        const fmt = (iso) => {
                          if (!iso) return '';
                          const d = new Date(iso);
                          if (Number.isNaN(d.getTime())) return '';
                          return formatHijriDate(d, { locale, includeWeekday: false });
                        };
                        const parts = [];
                        if (invForChip?.sent_at) parts.push(`${(t('invitationSentOn') || (isRTL ? 'أُرسلت في' : 'Sent on'))}: ${fmt(invForChip.sent_at)}`);
                        if (invForChip?.expires_at && chipStatus === 'pending') parts.push(`${(t('invitationExpiresOn') || (isRTL ? 'تنتهي في' : 'Expires on'))}: ${fmt(invForChip.expires_at)}`);
                        if (invForChip?.accepted_at) parts.push(`${(t('invitationAcceptedOn') || (isRTL ? 'قُبلت في' : 'Accepted on'))}: ${fmt(invForChip.accepted_at)}`);
                        if (chipStatus === 'accepted' && invForChip?.parent_name) {
                          const tmpl = t('invitationLinkedToParent') || (isRTL ? 'مرتبط بـ {0}' : 'Linked to {0}');
                          parts.push(tmpl.replace('{0}', invForChip.parent_name));
                        }
                        chipNode = (
                          <Badge
                            variant="outline"
                            className={`w-full justify-center text-[10px] mt-3 ${STATUS_STYLES_TOP[chipStatus]}`}
                            data-testid={`invite-status-${student.id}`}
                            title={parts.join('\n')}
                          >
                            {lbl}
                          </Badge>
                        );
                      }
                      if (pd.isLinked) {
                        return (
                          <>
                            {chipNode}
                            <Button
                              variant="outline"
                              size="sm"
                              className="w-full mt-3 text-xs gap-1.5 border-brand-turquoise/30 text-brand-navy hover:bg-brand-turquoise/10 hover:border-brand-turquoise"
                              onClick={(e) => openMessageParent(e, student)}
                            >
                              <MessageSquare className="h-3.5 w-3.5" />
                              {t('messageParent')}
                            </Button>
                          </>
                        );
                      }
                      if (isIndependentTeacher && hasPending) {
                        // Task #206 — §6.2c invitation status chip. Shown
                        // when the IT_PARENT_INVITATIONS_ENABLED flow has
                        // produced a parent_invitations row for this
                        // student. Falls back to the legacy badge when no
                        // invitation exists (the §5.6 immediate Pending
                        // → Linked path or pre-invitation state).
                        const inv = invitationByStudent[student.id];
                        const status = inv?.status || null;
                        const STATUS_STYLES = {
                          pending: 'text-amber-700 border-amber-300 bg-amber-50',
                          accepted: 'text-emerald-700 border-emerald-300 bg-emerald-50',
                          expired: 'text-gray-600 border-gray-300 bg-gray-50',
                          cancelled: 'text-gray-600 border-gray-300 bg-gray-50',
                        };
                        const STATUS_LABELS_AR = {
                          pending: 'دعوة معلّقة',
                          accepted: 'تم القبول',
                          expired: 'انتهت صلاحية الدعوة',
                          cancelled: 'تم إلغاء الدعوة',
                        };
                        const STATUS_LABELS_EN = {
                          pending: 'Invitation pending',
                          accepted: 'Parent linked',
                          expired: 'Invitation expired',
                          cancelled: 'Invitation cancelled',
                        };
                        const labelKey = status ? `parentInvitationStatus${status.charAt(0).toUpperCase()}${status.slice(1)}` : null;
                        const chipLabel = labelKey ? (t(labelKey) || (isRTL ? STATUS_LABELS_AR[status] : STATUS_LABELS_EN[status])) : null;
                        const chipClass = status
                          ? STATUS_STYLES[status]
                          : 'text-amber-700 border-amber-300 bg-amber-50';
                        const fallbackChip = isRTL ? 'لم يتم الربط بعد' : 'Not linked yet';
                        const showCancel = status === 'pending' && inv?.id;
                        return (
                          <div className="mt-3 space-y-2">
                            <Badge
                              variant="outline"
                              className={`w-full justify-center text-[10px] ${chipClass}`}
                              data-testid={`invite-status-${student.id}`}
                              title={(() => {
                                // Tooltip is built from i18n labels and
                                // hijri-formatted dates — never the
                                // browser `Intl` islamic calendar (per
                                // user-preferences in replit.md).
                                const locale = isRTL ? 'ar' : 'en';
                                const fmt = (iso) => {
                                  if (!iso) return '';
                                  const d = new Date(iso);
                                  if (Number.isNaN(d.getTime())) return '';
                                  return formatHijriDate(d, { locale, includeWeekday: false });
                                };
                                const parts = [];
                                if (inv?.sent_at) parts.push(`${(t('invitationSentOn') || (isRTL ? 'أُرسلت في' : 'Sent on'))}: ${fmt(inv.sent_at)}`);
                                if (inv?.expires_at && status === 'pending') parts.push(`${(t('invitationExpiresOn') || (isRTL ? 'تنتهي في' : 'Expires on'))}: ${fmt(inv.expires_at)}`);
                                if (inv?.accepted_at) parts.push(`${(t('invitationAcceptedOn') || (isRTL ? 'قُبلت في' : 'Accepted on'))}: ${fmt(inv.accepted_at)}`);
                                if (status === 'accepted' && inv?.parent_name) {
                                  const tmpl = t('invitationLinkedToParent') || (isRTL ? 'مرتبط بـ {0}' : 'Linked to {0}');
                                  parts.push(tmpl.replace('{0}', inv.parent_name));
                                }
                                return parts.join('\n');
                              })()}
                            >
                              {chipLabel || fallbackChip}
                            </Badge>
                            <Button
                              variant="outline"
                              size="sm"
                              className="w-full text-xs gap-1.5 border-brand-navy/30 text-brand-navy hover:bg-brand-navy/10 hover:border-brand-navy"
                              onClick={(e) => openInviteParent(e, student)}
                              data-testid={`invite-parent-${student.id}`}
                            >
                              <UserPlus className="h-3.5 w-3.5" />
                              {isRTL ? 'ربط ولي الأمر' : 'Invite parent'}
                            </Button>
                            {showCancel && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="w-full text-xs gap-1.5 text-red-600 hover:bg-red-50 hover:text-red-700"
                                onClick={(e) => { e.stopPropagation(); cancelInvitationForStudent(student); }}
                                data-testid={`invite-cancel-${student.id}`}
                              >
                                {t('cancelInvitation') || (isRTL ? 'إلغاء الدعوة' : 'Cancel invitation')}
                              </Button>
                            )}
                          </div>
                        );
                      }
                      return null;
                    })()}

                    {isIndependentTeacher && (
                      <div className="flex gap-1.5 mt-3 pt-2 border-t border-border/50">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="flex-1 h-7 text-xs"
                          onClick={(e) => handleEditStudent(e, student)}
                          data-testid={`student-edit-${student.id}`}
                        >
                          <Pencil className="h-3 w-3 me-1" />
                          {isRTL ? 'تعديل' : 'Edit'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="flex-1 h-7 text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={(e) => handleDeleteStudent(e, student)}
                          data-testid={`student-delete-${student.id}`}
                        >
                          <Trash2 className="h-3 w-3 me-1" />
                          {isRTL ? 'حذف' : 'Delete'}
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
            );
            return (
              <ResponsiveTable
                ariaLabel={t('students') || 'الطلاب'}
                rows={filteredStudents}
                getRowKey={(student) => student.id}
                cardClassName="p-0 border-0 bg-transparent"
                desktopMode="grid"
                columns={[{
                  key: 'student',
                  header: t('students') || 'الطلاب',
                  primary: true,
                  render: (student, idx) => renderStudentCard(student, idx),
                }]}
              />
            );
          })()}
        </div>

        {/* Message Parent Dialog */}
        <Dialog open={showMessageDialog} onOpenChange={setShowMessageDialog}>
          <DialogContent className="w-[95vw] max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-brand-turquoise" />
                {t('messageParent2')}
              </DialogTitle>
            </DialogHeader>
            {messageTarget && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                  <Avatar className="h-10 w-10">
                    <AvatarFallback className="bg-brand-navy text-white">
                      {messageTarget.full_name?.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium text-sm">{messageTarget.full_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {t('parent')}: {messageTarget.parent_name || messageTarget.parent_id}
                    </p>
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    {t('subject3')}
                  </label>
                  <Input
                    value={messageSubject}
                    onChange={(e) => setMessageSubject(e.target.value)}
                    placeholder={t('enterMessageSubject')}
                  />
                </div>

                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    {t('message2')}
                  </label>
                  <Textarea
                    value={messageBody}
                    onChange={(e) => setMessageBody(e.target.value)}
                    placeholder={t('typeYourMessageToTheParent')}
                    rows={5}
                  />
                </div>
              </div>
            )}
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setShowMessageDialog(false)}>
                {t('cancel')}
              </Button>
              <Button
                className="bg-brand-turquoise hover:bg-brand-turquoise/90 gap-1.5"
                onClick={handleSendParentMessage}
                disabled={sendingMessage}
              >
                {sendingMessage ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                {t('send')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Invite Parent Dialog (#199 spec §5.6 — atomic Pending → Linked) */}
        <Dialog open={inviteOpen} onOpenChange={(o) => { if (!inviteSubmitting) setInviteOpen(o); }}>
          <DialogContent className="w-[95vw] max-w-lg" data-testid="invite-parent-dialog">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Link2 className="h-5 w-5 text-brand-navy" />
                {isRTL ? 'ربط ولي الأمر' : 'Invite parent'}
              </DialogTitle>
            </DialogHeader>
            {inviteTarget && (
              <div className="space-y-3">
                <div className="text-xs text-muted-foreground">
                  {isRTL
                    ? 'يلزم رقم الجوال أو البريد الإلكتروني أو رقم الهوية على الأقل.'
                    : 'At least phone, email, or national ID is required.'}
                </div>
                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    {isRTL ? 'الاسم الكامل' : 'Full name'}
                  </label>
                  <Input
                    value={inviteForm.full_name}
                    onChange={(e) => setInviteForm({ ...inviteForm, full_name: e.target.value })}
                    placeholder={isRTL ? 'اسم ولي الأمر' : 'Parent name'}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      {isRTL ? 'رقم الجوال' : 'Phone'}
                    </label>
                    <Input
                      value={inviteForm.phone}
                      onChange={(e) => setInviteForm({ ...inviteForm, phone: e.target.value })}
                      placeholder="+9665XXXXXXXX"
                      data-testid="invite-parent-phone"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      {isRTL ? 'البريد الإلكتروني' : 'Email'}
                    </label>
                    <Input
                      type="email"
                      value={inviteForm.email}
                      onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                      placeholder="parent@example.com"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      {isRTL ? 'رقم الهوية' : 'National ID'}
                    </label>
                    <Input
                      value={inviteForm.national_id}
                      onChange={(e) => setInviteForm({ ...inviteForm, national_id: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      {isRTL ? 'صلة القرابة' : 'Relationship'}
                    </label>
                    <Select
                      value={inviteForm.relationship}
                      onValueChange={(v) => setInviteForm({ ...inviteForm, relationship: v })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="father">{isRTL ? 'الأب' : 'Father'}</SelectItem>
                        <SelectItem value="mother">{isRTL ? 'الأم' : 'Mother'}</SelectItem>
                        <SelectItem value="guardian">{isRTL ? 'ولي أمر' : 'Guardian'}</SelectItem>
                        <SelectItem value="other">{isRTL ? 'أخرى' : 'Other'}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            )}
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => setInviteOpen(false)}
                disabled={inviteSubmitting}
              >
                {t('cancel')}
              </Button>
              <Button
                className="bg-brand-navy hover:bg-brand-navy/90 gap-1.5 text-white"
                onClick={handleInviteParent}
                disabled={inviteSubmitting}
                data-testid="invite-parent-submit"
              >
                {inviteSubmitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <UserPlus className="h-4 w-4" />
                )}
                {isRTL ? 'ربط' : 'Link'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Student Details Dialog */}
        <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
          <DialogContent className="w-[95vw] max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-3">
                {selectedStudent && (
                  <>
                    <Avatar className="h-10 w-10">
                      <AvatarFallback className="bg-brand-navy text-white">
                        {selectedStudent.full_name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <p>{selectedStudent.full_name}</p>
                      <p className="text-sm text-muted-foreground font-normal">
                        {selectedStudent.student_id}
                      </p>
                    </div>
                    {selectedStudent.parent_id && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs gap-1.5 border-brand-turquoise/30 text-brand-navy hover:bg-brand-turquoise/10"
                        onClick={(e) => { setShowDetailsDialog(false); openMessageParent(e, selectedStudent); }}
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        {t('messageParent')}
                      </Button>
                    )}
                  </>
                )}
              </DialogTitle>
            </DialogHeader>
            
            {loadingDetails ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
              </div>
            ) : studentDetails && (
              <Tabs defaultValue="overview" className="mt-4">
                <TabsList className="grid grid-cols-3 sm:grid-cols-5 w-full">
                  <TabsTrigger value="overview">{t('overview')}</TabsTrigger>
                  <TabsTrigger value="attendance">{t('attendance2')}</TabsTrigger>
                  <TabsTrigger value="grades">{t('grades')}</TabsTrigger>
                  <TabsTrigger value="behavior">{t('behavior')}</TabsTrigger>
                  <TabsTrigger value="ai-insights" className="gap-1">
                    <Brain className="h-3.5 w-3.5" />
                    {isRTL ? 'تحليل ذكي' : 'AI Insights'}
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="space-y-4 mt-4">
                  <div className="grid grid-cols-2 gap-3">
                    <Card>
                      <CardContent className="p-4 text-center">
                        <ClipboardCheck className="h-7 w-7 mx-auto mb-1 text-green-600" />
                        <div className="text-2xl font-bold">{studentDetails?.attendance?.rate ?? selectedStudent?.attendance_rate ?? 0}%</div>
                        <div className="text-xs text-muted-foreground">{isRTL ? 'نسبة الحضور' : 'Attendance'}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <FileText className="h-7 w-7 mx-auto mb-1 text-blue-600" />
                        <div className="text-2xl font-bold">{studentDetails?.grades?.average ?? selectedStudent?.average_grade ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('avgGrade')}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <Star className="h-7 w-7 mx-auto mb-1 text-purple-600" />
                        <div className="text-2xl font-bold">{studentDetails?.behavior?.total_points ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('behaviorPts')}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <TrendingUp className="h-7 w-7 mx-auto mb-1 text-amber-600" />
                        <div className="text-2xl font-bold">{studentDetails?.participation?.participation_count ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('participations')}</div>
                      </CardContent>
                    </Card>
                  </div>

                  {(studentDetails?.skills || []).length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t('recordedSkills')}</CardTitle>
                      </CardHeader>
                      <CardContent className="flex flex-wrap gap-2">
                        {studentDetails.skills.slice(0, 8).map((skill, idx) => (
                          <Badge key={idx} variant="outline" className="text-xs">
                            {skill.skill_name} {skill.level ? `(${skill.level})` : ''}
                          </Badge>
                        ))}
                      </CardContent>
                    </Card>
                  )}

                  {(() => {
                    // Task #199 §5.6 read-precedence: linked parent
                    // fields when ``parent_id`` is set, else
                    // ``pending_parent_*`` for IT-workspace students.
                    const pd = getStudentParentDisplay(selectedStudent);
                    if (!pd.phone && !pd.email && !pd.name) return null;
                    return (
                      <Card>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm flex items-center gap-2">
                            {t('contactInfo')}
                            {pd.isLinked ? (
                              <Badge variant="outline" className="text-[10px] border-green-300 text-green-700">
                                {isRTL ? 'مرتبط' : 'Linked'}
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700">
                                {isRTL ? 'لم يتم الربط بعد' : 'Not yet linked'}
                              </Badge>
                            )}
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                          {pd.phone && (
                            <div className="flex items-center gap-2">
                              <Phone className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm">{pd.phone}</span>
                            </div>
                          )}
                          {pd.email && (
                            <div className="flex items-center gap-2">
                              <Mail className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm">{pd.email}</span>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })()}
                </TabsContent>

                <TabsContent value="attendance" className="mt-4 space-y-4">
                  <div className="grid grid-cols-3 gap-2">
                    <Card>
                      <CardContent className="p-3 text-center">
                        <div className="text-lg font-bold text-green-600">{studentDetails?.attendance?.present ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('present')}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-3 text-center">
                        <div className="text-lg font-bold text-red-600">{studentDetails?.attendance?.absent ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('absent')}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-3 text-center">
                        <div className="text-lg font-bold text-amber-600">{studentDetails?.attendance?.late ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('late')}</div>
                      </CardContent>
                    </Card>
                  </div>

                  {(studentDetails?.attendance?.trend || []).length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t('monthlyAttendanceTrend')}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {studentDetails.attendance.trend.map((item, idx) => (
                            <div key={idx} className="flex items-center gap-3">
                              <span className="text-xs w-16 text-muted-foreground">{item.month}</span>
                              <div className="flex-1">
                                <Progress value={item.rate} className="h-2" />
                              </div>
                              <span className="text-xs font-medium w-10 text-end">{item.rate}%</span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">{t('recentRecords')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {(studentDetails?.attendance?.recent || []).length === 0 ? (
                        <p className="text-center text-muted-foreground py-4 text-sm">
                          {t('noAttendanceRecords')}
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {studentDetails.attendance.recent.map((record, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                              <span className="text-sm">{new Date(record.date).toLocaleDateString('ar-SA')}</span>
                              <Badge variant={record.status === 'present' ? 'default' : 'destructive'}>
                                {record.status === 'present' ? (t('present')) :
                                 record.status === 'absent' ? (t('absent')) :
                                 (t('late'))}
                              </Badge>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="grades" className="mt-4 space-y-4">
                  {studentDetails?.grades?.average > 0 && (
                    <Card>
                      <CardContent className="p-4 flex items-center justify-between">
                        <span className="text-sm font-medium">{t('overallAverage')}</span>
                        <div className={`text-2xl font-bold ${getGradeColor(studentDetails.grades.average)}`}>
                          {studentDetails.grades.average}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                  <Card>
                    <CardContent className="p-4">
                      {(studentDetails?.grades?.records || []).length === 0 ? (
                        <p className="text-center text-muted-foreground py-4 text-sm">
                          {t('noGrades')}
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {studentDetails.grades.records.map((grade, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                              <div>
                                <p className="font-medium text-sm">{grade.assessment_name || grade.subject_name}</p>
                                <p className="text-xs text-muted-foreground">{grade.type || (t('assessment'))}</p>
                              </div>
                              <Badge className={getGradeColor(grade.score || 0)}>
                                {grade.score || 0} / {grade.max_score || 100}
                              </Badge>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="behavior" className="mt-4 space-y-4">
                  <Card>
                    <CardContent className="p-4 flex items-center justify-between">
                      <span className="text-sm font-medium">{t('totalPoints2')}</span>
                      <div className={`text-2xl font-bold ${(studentDetails?.behavior?.total_points ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {(studentDetails?.behavior?.total_points ?? 0) >= 0 ? '+' : ''}{studentDetails?.behavior?.total_points ?? 0}
                      </div>
                    </CardContent>
                  </Card>

                  {(studentDetails?.participation?.recent || []).length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t('sessionInteractions')}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {studentDetails.participation.recent.slice(0, 5).map((inter, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                              <div>
                                <p className="text-sm font-medium">{inter.note || inter.type}</p>
                                <p className="text-xs text-muted-foreground">{inter.created_at ? new Date(inter.created_at).toLocaleDateString('ar-SA') : ''}</p>
                              </div>
                              {inter.points != null && (
                                <Badge variant={inter.points > 0 ? 'default' : 'destructive'}>
                                  {inter.points > 0 ? '+' : ''}{inter.points}
                                </Badge>
                              )}
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">{t('behaviorRecords2')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {(studentDetails?.behavior?.records || []).length === 0 && (studentDetails?.behavior?.session_records || []).length === 0 ? (
                        <p className="text-center text-muted-foreground py-4 text-sm">
                          {t('noBehaviorRecords3')}
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {[...(studentDetails?.behavior?.records || []), ...(studentDetails?.behavior?.session_records || [])].slice(0, 10).map((record, idx) => (
                            <div 
                              key={idx} 
                              className={`p-2 rounded ${
                                (record.points || 0) > 0 ? 'bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800'
                              } border`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-medium text-sm">{record.note || (t('note'))}</span>
                                <Badge variant={(record.points || 0) > 0 ? 'default' : 'destructive'}>
                                  {(record.points || 0) > 0 ? '+' : ''}{record.points || 0}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">
                                {record.date ? new Date(record.date).toLocaleDateString('ar-SA') : 
                                 record.created_at ? new Date(record.created_at).toLocaleDateString('ar-SA') : ''}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="ai-insights" className="mt-4 space-y-4">
                  {loadingAI ? (
                    <div className="flex flex-col items-center justify-center py-10">
                      <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise mb-3" />
                      <p className="text-sm text-muted-foreground">{t('analyzingStudentData')}</p>
                    </div>
                  ) : aiInsights ? (
                    <>
                      <Card className="border-brand-turquoise/30 bg-gradient-to-br from-brand-turquoise/5 to-transparent">
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <Activity className="h-5 w-5 text-brand-turquoise" />
                              <h4 className="font-bold font-cairo">{t('riskAssessment')}</h4>
                            </div>
                            <Badge className={`${
                              aiInsights.risk_assessment?.category === 'low' ? 'bg-green-100 text-green-700' :
                              aiInsights.risk_assessment?.category === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                              aiInsights.risk_assessment?.category === 'high' ? 'bg-orange-100 text-orange-700' :
                              'bg-red-100 text-red-700'
                            }`}>
                              {aiInsights.risk_assessment?.label_ar || aiInsights.risk_assessment?.category}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3">
                            <div className="text-3xl font-bold text-brand-turquoise">{Math.round(aiInsights.risk_assessment?.score || 0)}%</div>
                            <div className="flex-1">
                              <Progress value={aiInsights.risk_assessment?.score || 0} className="h-2" />
                              <p className="text-xs text-muted-foreground mt-1">{t('stabilityIndexHigherBetter')}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <Card className="border-green-200 dark:border-green-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2 text-green-700 dark:text-green-400">
                              <ArrowUpCircle className="h-4 w-4" />
                              {t('strengths')}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            {(aiInsights.strengths || []).length > 0 ? (
                              <div className="space-y-2">
                                {aiInsights.strengths.map((s, idx) => (
                                  <div key={idx} className="flex items-center gap-2 p-2 rounded-lg bg-green-50 dark:bg-green-950/30">
                                    <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />
                                    <span className="text-sm font-cairo">{s}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-muted-foreground text-center py-3">
                                {t('notEnoughData')}
                              </p>
                            )}
                          </CardContent>
                        </Card>

                        <Card className="border-red-200 dark:border-red-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2 text-red-700 dark:text-red-400">
                              <ArrowDownCircle className="h-4 w-4" />
                              {t('areasForImprovement')}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            {(aiInsights.weaknesses || []).length > 0 ? (
                              <div className="space-y-2">
                                {aiInsights.weaknesses.map((w, idx) => (
                                  <div key={idx} className="flex items-center gap-2 p-2 rounded-lg bg-red-50 dark:bg-red-950/30">
                                    <AlertTriangle className="h-4 w-4 text-red-500 shrink-0" />
                                    <span className="text-sm font-cairo">{w}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-muted-foreground text-center py-3">
                                {t('noConcerns')}
                              </p>
                            )}
                          </CardContent>
                        </Card>
                      </div>

                      {(aiInsights.goals || []).length > 0 && (
                        <Card className="border-blue-200 dark:border-blue-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2 text-blue-700 dark:text-blue-400">
                              <Target className="h-4 w-4" />
                              {t('suggestedGoals')}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-2">
                              {aiInsights.goals.map((g, idx) => (
                                <div key={idx} className="flex items-start gap-2 p-2 rounded-lg bg-blue-50 dark:bg-blue-950/30">
                                  <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-xs font-bold text-blue-700 shrink-0 mt-0.5">
                                    {idx + 1}
                                  </div>
                                  <div>
                                    <p className="text-sm font-cairo font-medium">{g.goal_ar}</p>
                                    {g.target != null && (
                                      <p className="text-xs text-muted-foreground mt-0.5">
                                        {isRTL ? `الهدف: ${g.target}${g.metric?.includes('rate') || g.metric?.includes('average') ? '%' : ''}` : `Target: ${g.target}`}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}

                      {aiInsights.action_plan?.actions?.length > 0 && (
                        <Card className="border-purple-200 dark:border-purple-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2 text-purple-700 dark:text-purple-400">
                              <Lightbulb className="h-4 w-4" />
                              {t('improvementEnrichmentPlan')}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-3">
                              {aiInsights.action_plan.actions.map((action, idx) => (
                                <div key={idx} className="p-3 rounded-lg border bg-gradient-to-r from-purple-50/50 to-transparent dark:from-purple-950/20">
                                  <div className="flex items-start justify-between mb-1">
                                    <div className="flex items-center gap-2">
                                      <Sparkles className="h-4 w-4 text-purple-600 shrink-0" />
                                      <h5 className="font-medium text-sm font-cairo">{action.title_ar}</h5>
                                    </div>
                                    <Badge variant="outline" className="text-[10px] shrink-0">
                                      {action.deadline_days} {t('days')}
                                    </Badge>
                                  </div>
                                  <p className="text-xs text-muted-foreground font-cairo ps-6">{action.description_ar}</p>
                                  <p className="text-[10px] text-brand-turquoise font-cairo ps-6 mt-1">
                                    {t('responsible')}
                                    {action.responsible === 'class_teacher' ? (isRTL ? 'معلم الفصل' : 'Class Teacher') :
                                     action.responsible === 'subject_teachers' ? (t('subjectTeachers')) :
                                     action.responsible === 'counselor' ? (t('counselor')) :
                                     action.responsible === 'school_principal' ? (t('principal')) :
                                     action.responsible}
                                  </p>
                                </div>
                              ))}
                            </div>
                            {aiInsights.review_date && (
                              <div className="mt-3 p-2 rounded bg-muted/50 text-center">
                                <p className="text-xs text-muted-foreground font-cairo">
                                  {isRTL ? `موعد المراجعة التالية: ${aiInsights.review_date}` : `Next review: ${aiInsights.review_date}`}
                                </p>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      )}

                      <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
                        <span className="font-cairo">
                          {isRTL ? `اتجاه الدرجات: ${
                            aiInsights.grade_trend === 'improving' ? '📈 تحسن' :
                            aiInsights.grade_trend === 'declining' ? '📉 تراجع' : '➡️ مستقر'
                          }` : `Grade trend: ${aiInsights.grade_trend || 'stable'}`}
                        </span>
                        <Button variant="ghost" size="sm" onClick={() => fetchAIInsights(selectedStudent?.id)} className="h-7 text-xs">
                          <RefreshCw className="h-3 w-3 me-1" />
                          {t('refresh')}
                        </Button>
                      </div>
                    </>
                  ) : (
                    <Card className="p-8 text-center">
                      <Brain className="h-12 w-12 mx-auto text-muted-foreground/30 mb-3" />
                      <p className="text-muted-foreground text-sm font-cairo">
                        {t('notEnoughDataAvailableForAnalysisTheSystemNeedsAtt')}
                      </p>
                      <Button variant="outline" size="sm" className="mt-3" onClick={() => fetchAIInsights(selectedStudent?.id)}>
                        <Brain className="h-3.5 w-3.5 me-1" />
                        {isRTL ? 'إعادة المحاولة' : 'Try Again'}
                      </Button>
                    </Card>
                  )}
                </TabsContent>
              </Tabs>
            )}
          </DialogContent>
        </Dialog>

        {/* Edit student dialog (IT only — Task #185) */}
        <Dialog open={!!editStudentDialog} onOpenChange={(o) => !o && setEditStudentDialog(null)}>
          <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Pencil className="h-5 w-5 text-brand-turquoise" />
                {isRTL ? 'تعديل بيانات الطالب' : 'Edit student'}
              </DialogTitle>
            </DialogHeader>
            {editStudentDialog && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="font-cairo text-sm">{isRTL ? 'الاسم الكامل' : 'Full name'}</label>
                  <Input
                    value={editStudentDialog.full_name}
                    onChange={(e) => setEditStudentDialog((p) => ({ ...p, full_name: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="font-cairo text-sm">{isRTL ? 'الصف' : 'Grade'}</label>
                  <Input
                    value={editStudentDialog.grade}
                    onChange={(e) => setEditStudentDialog((p) => ({ ...p, grade: e.target.value }))}
                  />
                </div>
                {/* 2026-05-19 — Class dropdown for IT users. Replaces the
                    "no way to assign" gap that left imported students stuck
                    in the "غير معينين" filter. Populated from
                    `workspaceClasses` (GET /classes, IT-tenant-scoped on
                    the backend), with an "غير معين" sentinel to clear the
                    assignment. Disabled with helper copy when the teacher
                    hasn't created any classes yet. */}
                {isIndependentTeacher && (
                  <div className="space-y-2">
                    <label className="font-cairo text-sm">{isRTL ? 'الفصل' : 'Class'}</label>
                    {/* 2026-05-19 — Empty-classes state must surface the
                        helper copy *outside* the Select. Radix `Select`
                        renders its currently-selected item label, not
                        the trigger placeholder, when a value is bound —
                        so the original placeholder-based approach kept
                        showing "غير معين" instead of guiding the teacher
                        to create a class first. Render a disabled,
                        input-styled banner in that case. */}
                    {workspaceClasses.length === 0 ? (
                      <div
                        className="flex h-10 w-full items-center rounded-md border border-input bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
                        data-testid="edit-student-class-empty"
                      >
                        {isRTL ? 'لم تقم بإنشاء فصول بعد' : 'No classes created yet'}
                      </div>
                    ) : (
                      <Select
                        value={editStudentDialog.class_id || 'unassigned'}
                        onValueChange={(v) => setEditStudentDialog((p) => ({ ...p, class_id: v }))}
                      >
                        <SelectTrigger data-testid="edit-student-class-select">
                          <SelectValue placeholder={isRTL ? 'اختر فصلاً' : 'Select a class'} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="unassigned">
                            {isRTL ? 'غير معين' : 'Unassigned'}
                          </SelectItem>
                          {workspaceClasses.map((cls) => (
                            <SelectItem key={cls.id} value={cls.id}>
                              {cls.name || cls.name_ar || cls.id}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                )}
                <div className="space-y-2">
                  <label className="font-cairo text-sm">{isRTL ? 'الجنس' : 'Gender'}</label>
                  <Select
                    value={editStudentDialog.gender || ''}
                    onValueChange={(v) => setEditStudentDialog((p) => ({ ...p, gender: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={isRTL ? 'اختر' : 'Select'} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="male">{isRTL ? 'ذكر' : 'Male'}</SelectItem>
                      <SelectItem value="female">{isRTL ? 'أنثى' : 'Female'}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditStudentDialog(null)}>{t('cancel')}</Button>
              <Button onClick={saveEditStudent} disabled={editStudentSaving}>
                {editStudentSaving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : null}
                {t('save') || (isRTL ? 'حفظ' : 'Save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {isIndependentTeacher && (
          <AddStudentWizard
            open={showAddStudent}
            onOpenChange={setShowAddStudent}
            onSuccess={handleAddStudentSuccess}
            api={api}
            isRTL={isRTL}
            grades={workspaceGrades}
            classes={workspaceClasses}
            mode="workspace"
          />
        )}
      </div>
      {!embedded && <HakimAssistant />}
    </Shell>
  );
}
