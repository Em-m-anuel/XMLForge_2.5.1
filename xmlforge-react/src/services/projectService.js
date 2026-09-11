import apiClient from './api'

export const projectService = {
  exportProject: async (databaseId, { download = false, name } = {}) => {
    if (download) return apiClient.download(`/export/project/${databaseId}?download=true`, `${name || `project_${databaseId}`}.xml`)
    return (await apiClient.get(`/export/project/${databaseId}`)).data
  },
  exportProjectXml: async (databaseId) => (await apiClient.get(`/export/project/${databaseId}`)).data,
  importProject: async (fileOrXml) => {
    if (typeof File !== 'undefined' && fileOrXml instanceof File) {
      const form = new FormData()
      form.append('file', fileOrXml)
      return (await apiClient.post('/import/project', form)).data
    }
    return (await apiClient.post('/import/project', { xml: fileOrXml })).data
  },
}
