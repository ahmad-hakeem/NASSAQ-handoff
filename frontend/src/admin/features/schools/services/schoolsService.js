/**
 * Schools Management Admin API Service
 * Centralized API service for all school operations in Platform Admin
 */

export const schoolsService = {
  /**
   * Fetch paginated and filtered schools list
   */
  async fetchSchools(api, params = {}) {
    const res = await api.get('/schools', { params });
    const rawData = res.data || {};
    const schools = Array.isArray(rawData) ? rawData : (rawData.schools || []);
    const total = rawData.total !== undefined ? rawData.total : schools.length;
    const limit = params?.limit || 10;
    const totalPages = rawData.total_pages || Math.ceil(total / limit) || 1;

    return {
      schools,
      total,
      totalPages,
      cities: rawData.cities || [],
      raw: rawData,
    };
  },

  /**
   * Fetch platform-level aggregated school numbers & metrics
   */
  async fetchSchoolNumbers(api) {
    const res = await api.get('/schools/numbers');
    return res.data || {};
  },

  /**
   * Fetch draft / setup-phase schools
   */
  async fetchSchoolDrafts(api) {
    const res = await api.get('/schools/draft');
    return Array.isArray(res.data) ? res.data : [];
  },

  /**
   * Fetch a single draft or school details
   */
  async fetchSchoolDraftById(api, draftId) {
    const res = await api.get(`/schools/${draftId}`);
    return res.data;
  },

  /**
   * Delete a draft school
   */
  async deleteSchoolDraft(api, draftId) {
    const res = await api.delete(`/schools/${draftId}/draft`);
    return res.data;
  },

  /**
   * Temporarily suspend a school
   */
  async suspendSchool(api, schoolId, reason) {
    const res = await api.post(`/schools/${schoolId}/suspend`, { reason });
    return res.data;
  },

  /**
   * Reactivate a suspended school
   */
  async activateSchool(api, schoolId, reason) {
    const res = await api.post(`/schools/${schoolId}/activate`, { reason });
    return res.data;
  },

  /**
   * Fetch complete detail dossier for a school
   */
  async fetchSchoolDetail(api, schoolId) {
    const res = await api.get(`/schools/${schoolId}/detail`);
    return res.data;
  },

  /**
   * Update general info for a school
   */
  async updateSchool(api, schoolId, data) {
    const res = await api.put(`/schools/${schoolId}`, data);
    return res.data;
  },

  /**
   * Create or reset principal credentials for a school
   */
  async saveSchoolCredentials(api, schoolId, payload) {
    const res = await api.post(`/schools/${schoolId}/credentials`, payload);
    return res.data;
  },

  /**
   * Fetch all schools for complete export (unpaginated)
   */
  async fetchAllSchoolsForExport(api) {
    const res = await api.get('/schools');
    if (Array.isArray(res.data)) {
      return res.data;
    }
    if (res.data?.schools && Array.isArray(res.data.schools)) {
      return res.data.schools;
    }
    return [];
  },
};

export default schoolsService;
