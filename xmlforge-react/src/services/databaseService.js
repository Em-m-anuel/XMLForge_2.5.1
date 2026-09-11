import apiClient from './api'

function withVersion(payload = {}, expectedVersion) {
  return expectedVersion == null ? payload : { ...payload, expected_version: expectedVersion }
}

export const databaseService = {
  list: async (includeArchived = true) => {
    const response = await apiClient.get(`/databases?include_archived=${includeArchived}`)
    return response.data
  },
  get: async (id) => (await apiClient.get(`/databases/${id}`)).data,
  create: async ({ name, description = '', comment = '', scope = 'PERSONAL', common_permission = null }) => (
    await apiClient.post('/databases', { name, description, comment, scope, common_permission })
  ).data,
  update: async (id, payload, expectedVersion) => (
    await apiClient.put(`/databases/${id}`, withVersion(payload, expectedVersion))
  ).data,
  delete: async (id) => (await apiClient.delete(`/databases/${id}`)).data,
  archive: async (id) => (await apiClient.post(`/databases/${id}/archive`)).data,
  restore: async (id) => (await apiClient.post(`/databases/${id}/restore`)).data,
}
