export function createApiService(api) {
  return {
    auth: {
      me: () => api.get('/auth/me'),
      login: (email, password) => api.post('/auth/login', { email, password }),
      register: (data) => api.post('/auth/register', data),
      updatePreferences: (prefs) => api.put('/auth/preferences', null, { params: prefs }),
    },

    schools: {
      list: () => api.get('/schools'),
      get: (id) => api.get(`/schools/${id}`),
      create: (data) => api.post('/schools', data),
      update: (id, data) => api.put(`/schools/${id}`, data),
      dashboard: () => api.get('/school/dashboard-stats'),
    },

    students: {
      list: (params) => api.get('/students', { params }),
      get: (id) => api.get(`/students/${id}`),
      create: (data) => api.post('/students', data),
      update: (id, data) => api.put(`/students/${id}`, data),
      delete: (id) => api.delete(`/students/${id}`),
      bulkImport: (formData) => api.post('/students/bulk-import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),
    },

    teachers: {
      list: (params) => api.get('/teachers', { params }),
      get: (id) => api.get(`/teachers/${id}`),
      create: (data) => api.post('/teachers', data),
      update: (id, data) => api.put(`/teachers/${id}`, data),
      delete: (id) => api.delete(`/teachers/${id}`),
    },

    classes: {
      list: (params) => api.get('/classes', { params }),
      get: (id) => api.get(`/classes/${id}`),
      create: (data) => api.post('/classes', data),
      update: (id, data) => api.put(`/classes/${id}`, data),
      delete: (id) => api.delete(`/classes/${id}`),
    },

    subjects: {
      list: (params) => api.get('/subjects', { params }),
      create: (data) => api.post('/subjects', data),
      update: (id, data) => api.put(`/subjects/${id}`, data),
      delete: (id) => api.delete(`/subjects/${id}`),
    },

    attendance: {
      record: (data) => api.post('/attendance', data),
      get: (params) => api.get('/attendance', { params }),
      stats: (params) => api.get('/attendance/stats', { params }),
    },

    assessments: {
      list: (params) => api.get('/assessments', { params }),
      create: (data) => api.post('/assessments', data),
      update: (id, data) => api.put(`/assessments/${id}`, data),
    },

    notifications: {
      list: (params) => api.get('/notifications', { params }),
      markRead: (id) => api.put(`/notifications/${id}/read`),
      markAllRead: () => api.put('/notifications/read-all'),
    },

    settings: {
      getGeneral: () => api.get('/settings/general'),
      updateGeneral: (data) => api.put('/settings/general', data),
      getContact: () => api.get('/settings/contact'),
      updateContact: (data) => api.put('/settings/contact', data),
      getSecurity: () => api.get('/settings/security'),
      updateSecurity: (data) => api.put('/settings/security', data),
      getAccount: () => api.get('/settings/account'),
      updateAccount: (data) => api.put('/settings/account', data),
    },

    platform: {
      dashboardStats: () => api.get('/super-admin/dashboard-stats'),
      analytics: () => api.get('/platform/analytics'),
      growthData: (months) => api.get(`/platform/analytics/growth?months=${months || 6}`),
    },

    productHub: {
      list: (params) => api.get('/product-hub/issues', { params }),
      get: (id) => api.get(`/product-hub/issues/${id}`),
      create: (data) => api.post('/product-hub/issues', data),
      update: (id, data) => api.put(`/product-hub/issues/${id}`, data),
      addComment: (id, data) => api.post(`/product-hub/issues/${id}/comments`, data),
    },

    hakim: {
      analyze: (data) => api.post('/hakim/analyze', data),
      chat: (data) => api.post('/hakim/chat', data),
    },
  };
}
