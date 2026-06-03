/**
 * Platform-admin "Open Dashboard" / principal preview helpers.
 * Mirrors backend/utils/platform_admin_preview.py reason codes.
 */

const PREVIEW_MESSAGES_AR = {
  independent_teacher_workspace:
    'عذرًا، لا يمكن فتح هذا الحساب من هذا المسار حاليًا لأنه يمثل مساحة معلم مستقل وليس مدرسة. يرجى استخدام مسار إدارة المعلمين المستقلين أو مراجعة إدارة النظام.',
  archived:
    'عذرًا، لا يمكن فتح هذا الحساب من هذا المسار حاليًا لأن المدرسة مؤرشفة ولا تدعم المعاينة كلوحة مدرسة. يرجى مراجعة إدارة النظام أو استخدام المسار المناسب.',
  pending_hard_delete:
    'عذرًا، لا يمكن فتح هذا الحساب من هذا المسار حاليًا لأنه قيد الإجراء للحذف ولا يدعم المعاينة كلوحة مدرسة. يرجى مراجعة إدارة النظام.',
  no_active_principal:
    'لا يوجد مدير مدرسة نشط في هذه المدرسة — يرجى إضافة مدير قبل المعاينة.',
};

const PREVIEW_MESSAGES_EN = {
  independent_teacher_workspace:
    'This record is an independent-teacher workspace, not a school. Use the independent-teacher management path or contact platform support.',
  archived:
    'This school is archived and cannot be previewed as a principal dashboard from here.',
  pending_hard_delete:
    'This record is pending permanent deletion and cannot be previewed.',
  no_active_principal:
    'There is no active school principal for this school. Add a principal before previewing.',
};

export function getPreviewBlockMessage(school, { isRTL = true } = {}) {
  const reason = school?.preview_block_reason;
  if (!reason) return null;
  const table = isRTL ? PREVIEW_MESSAGES_AR : PREVIEW_MESSAGES_EN;
  return (
    table[reason] ||
    (isRTL
      ? 'عذرًا، لا يمكن فتح هذا الحساب من هذا المسار حاليًا لأن نوعه لا يدعم المعاينة كلوحة مدرسة. يرجى مراجعة إدارة النظام أو استخدام المسار المناسب.'
      : 'This account cannot be opened as a school dashboard from here. Please use the appropriate management path.')
  );
}

export function canOpenPrincipalDashboard(school) {
  if (!school?.id) return false;
  if (school.can_preview_as_principal === false) return false;
  if (school.entity_kind === 'independent_teacher_workspace') return false;
  const id = String(school.id);
  if (id.startsWith('itw_')) return false;
  const status = (school.status || '').toLowerCase();
  if (status === 'archived' || status === 'pending_hard_delete') return false;
  return true;
}

export function isIndependentTeacherWorkspaceRow(school) {
  return (
    school?.entity_kind === 'independent_teacher_workspace' ||
    String(school?.id || '').startsWith('itw_')
  );
}
