/**
 * Canonical evidence-type registry for ملف الإنجاز (teacher portfolio).
 *
 * Mirrors `EVIDENCE_SUBSECTIONS_V2` + the legacy-only types still accepted by
 * `ALL_EVIDENCE_TYPES` in backend/engines/portfolio_evidence_engine.py.
 *
 * Every type the backend can store MUST appear here: the file-library filter
 * and the evidence dialogs build their options from this list, so a missing
 * type means documents of that type can never be matched by any filter option
 * (the "نتائج الاختبارات returns nothing" bug — the library held
 * curriculum_distribution_plan / oral_assessment / exam_results_analysis
 * documents while the dropdown still offered the legacy 25-type vocabulary).
 *
 * backend/tests/test_portfolio_evidence_type_parity.py fails if the two
 * vocabularies drift apart again.
 */

// Arabic labels for the v2 vocabulary (the spec is Arabic-native).
export const TYPE_LABEL_AR = {
  // planning
  curriculum_distribution_plan: 'خطة توزيع المنهج',
  weekly_plan: 'الخطة الأسبوعية',
  lesson_plan: 'خطة الدرس',
  preparation_record: 'سجل التحضير',
  unit_plan: 'خطة وحدة دراسية',
  classroom_activity_plan: 'خطة النشاط الصفي',
  struggling_student_plan: 'خطة دعم المتعثرين',
  gifted_student_plan: 'خطة رعاية المتفوقين',
  learning_loss_plan: 'خطة معالجة الفاقد التعليمي',
  // execution
  classroom_activity_photos: 'صور أنشطة صفية',
  student_worksheets: 'أوراق عمل الطلاب',
  applied_lesson_report: 'تقرير درس تطبيقي',
  lesson_video_recording: 'تسجيل فيديو لدرس',
  collaborative_lesson: 'أنشطة تعاونية',
  teaching_strategies: 'استراتيجيات تدريس',
  // assessment
  exam_results: 'الاختبارات',
  quiz_results: 'الاختبارات القصيرة',
  assessment_worksheet: 'أوراق العمل التقويمية',
  performance_task: 'المهام الأدائية',
  student_portfolio_files: 'ملفات إنجاز الطلاب',
  student_project: 'مشاريع الطلاب',
  oral_assessment: 'التقويم الشفهي',
  classroom_observation: 'الملاحظة الصفية',
  // results
  exam_results_analysis: 'تحليل نتائج الاختبارات',
  class_results_analysis: 'تحليل نتائج الفصل',
  student_progress_report: 'تقارير تقدم الطلاب',
  grade_analysis_tables: 'جداول تحليل الدرجات',
  before_after_comparison: 'مقارنة النتائج قبل وبعد',
  results_improvement_plan: 'خطة تحسين النتائج',
  // community
  parent_communication_log: 'سجل التواصل مع أولياء الأمور',
  parent_meeting_minutes: 'تقرير اجتماع مع أولياء الأمور',
  school_activity_participation: 'مشاركة في نشاط مدرسي',
  school_event_participation: 'مشاركة في الفعاليات المدرسية',
  // professional development
  training_attendance_report: 'تقرير حضور دورة',
  professional_growth_plan: 'خطة تطوير مهني',
  plc_participation: 'مجتمعات التعلم المهنية',
  peer_observation: 'تبادل الزيارات',
  workshop_attendance: 'حضور ورش عمل',
  workshop_delivery: 'تقديم ورش',
  volunteer_activity_report: 'تقرير نشاط تطوعي',
};

// i18n keys for the legacy vocabulary. Types that the v2 map already covers
// keep their v2 label so the dropdown and the cards can never disagree.
export const LEGACY_TYPE_LABEL_KEYS = {
  lesson_plan: 'portfolioLessonPlan',
  weekly_plan: 'portfolioWeeklyPlan',
  unit_plan: 'portfolioUnitPlan',
  applied_lesson_report: 'portfolioAppliedLessonReport',
  collaborative_lesson: 'portfolioCollaborativeLesson',
  exam_results: 'portfolioExamResults',
  quiz_results: 'portfolioQuizResults',
  performance_task: 'portfolioPerformanceTask',
  exam_results_analysis: 'portfolioExamResultsAnalysis',
  grade_analysis_tables: 'portfolioGradeAnalysisTables',
  attendance_record: 'portfolioAttendanceRecord',
  late_tracking: 'portfolioLateTracking',
  behaviour_tracking: 'portfolioBehaviourTracking',
  struggling_student_plan: 'portfolioStrugglingStudentPlan',
  observation_notes: 'portfolioObservationNotes',
  parent_communication_log: 'portfolioParentCommunicationLog',
  parent_meeting_minutes: 'portfolioParentMeetingMinutes',
  training_certificate: 'portfolioTrainingCertificate',
  workshop_attendance: 'portfolioWorkshopAttendance',
  peer_observation: 'portfolioPeerObservation',
  participation_tracking: 'portfolioParticipationTracking',
  extracurricular_activity: 'portfolioExtracurricularActivity',
  annual_goals: 'portfolioAnnualGoals',
  self_evaluation: 'portfolioSelfEvaluation',
  professional_growth_plan: 'portfolioProfessionalGrowthPlan',
};

// The six v2 sub-sections shown under "شواهد الأداء الوظيفي", plus the legacy
// types that never got a v2 home but are still stored (attendance_record and
// behaviour_tracking have thousands of auto-captured rows).
export const EVIDENCE_TYPE_GROUPS = [
  {
    key: 'planning', title: 'شواهد التخطيط',
    types: ['curriculum_distribution_plan', 'weekly_plan', 'lesson_plan', 'preparation_record', 'unit_plan', 'classroom_activity_plan', 'struggling_student_plan', 'gifted_student_plan', 'learning_loss_plan'],
  },
  {
    key: 'execution', title: 'شواهد التنفيذ',
    types: ['classroom_activity_photos', 'student_worksheets', 'applied_lesson_report', 'lesson_video_recording', 'collaborative_lesson', 'teaching_strategies'],
  },
  {
    key: 'assessment', title: 'شواهد التقويم',
    types: ['exam_results', 'quiz_results', 'assessment_worksheet', 'performance_task', 'student_portfolio_files', 'student_project', 'oral_assessment', 'classroom_observation'],
  },
  {
    key: 'results', title: 'شواهد النتائج',
    types: ['exam_results_analysis', 'class_results_analysis', 'student_progress_report', 'grade_analysis_tables', 'before_after_comparison', 'results_improvement_plan'],
  },
  {
    key: 'community', title: 'شواهد التواصل والمجتمع',
    types: ['parent_communication_log', 'parent_meeting_minutes', 'school_activity_participation', 'school_event_participation'],
  },
  {
    key: 'professional_development', title: 'شواهد التطوير المهني',
    types: ['training_attendance_report', 'professional_growth_plan', 'plc_participation', 'peer_observation', 'workshop_attendance', 'workshop_delivery', 'volunteer_activity_report'],
  },
  {
    key: 'other', title: 'شواهد أخرى',
    types: ['attendance_record', 'late_tracking', 'behaviour_tracking', 'observation_notes', 'training_certificate', 'participation_tracking', 'extracurricular_activity', 'annual_goals', 'self_evaluation'],
  },
];

// Sub-sections the v2 UI renders (everything except the legacy catch-all).
export const V2_SUBSECTIONS = EVIDENCE_TYPE_GROUPS.filter(g => g.key !== 'other');

export const ALL_EVIDENCE_TYPES = EVIDENCE_TYPE_GROUPS.flatMap(g => g.types);

/**
 * One label per type, used by the cards, the filter options and the dialogs so
 * a teacher can always pick the exact wording printed on a document.
 * `t` is optional; without it legacy-only types fall back to their key-free
 * generic label rather than leaking an i18n key into the UI.
 */
export const labelForType = (typeKey, t) => {
  if (TYPE_LABEL_AR[typeKey]) return TYPE_LABEL_AR[typeKey];
  const i18nKey = LEGACY_TYPE_LABEL_KEYS[typeKey];
  if (i18nKey && typeof t === 'function') {
    const translated = t(i18nKey);
    // i18next returns the key itself when it is missing — never show that.
    if (translated && translated !== i18nKey) return translated;
  }
  return 'مستند تعليمي';
};
