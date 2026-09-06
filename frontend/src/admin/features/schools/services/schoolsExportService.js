/**
 * Schools Export Service
 * Formats schools datasets into CSV with UTF-8 BOM and triggers browser download
 */

export const schoolsExportService = {
  /**
   * Export an array of schools into a CSV file
   * @param {Array} schools - Array of school objects
   * @param {boolean} isRTL - Localization direction
   * @param {Object} statusMap - Mapping of status keys to labels
   */
  exportSchoolsToCSV(schools = [], isRTL = true, statusMap = {}) {
    const headers = isRTL
      ? ['اسم المدرسة', 'كود المدرسة', 'المدينة', 'المنطقة', 'الحالة', 'نوع المدرسة', 'المرحلة', 'عدد الطلاب', 'عدد المعلمين', 'عدد الفصول']
      : ['School Name', 'School Code', 'City', 'Region', 'Status', 'School Type', 'Stage', 'Students', 'Teachers', 'Classes'];

    const rows = schools.map(s => {
      const statusLabel = statusMap[s.status]?.label || s.status || '';
      const schoolTypeLabel = s.school_type === 'private'
        ? (isRTL ? 'أهلية' : 'Private')
        : (isRTL ? 'حكومية' : 'Public');

      const escapeCSV = (val) => `"${String(val || '').replace(/"/g, '""')}"`;

      return [
        escapeCSV(s.name),
        escapeCSV(s.code),
        escapeCSV(s.city),
        escapeCSV(s.region),
        escapeCSV(statusLabel),
        escapeCSV(schoolTypeLabel),
        escapeCSV(s.stage),
        s.student_count || s.current_students || 0,
        s.teacher_count || s.current_teachers || 0,
        s.class_count || 0,
      ];
    });

    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `schools_export_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};

export default schoolsExportService;
