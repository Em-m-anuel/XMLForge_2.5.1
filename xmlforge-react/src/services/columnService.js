import apiClient from './api'

const versioned = (payload = {}, expectedVersion) => expectedVersion == null ? payload : { ...payload, expected_version: expectedVersion }

export const columnService = {
  list: async (tableId, includeArchived = true) => (
    await apiClient.get(`/columns/${tableId}?include_archived=${includeArchived}`)
  ).data,
  get: async (columnId) => (await apiClient.get(`/columns/${columnId}/detail`)).data,
  create: async (payload, expectedVersion) => (
    await apiClient.post('/columns', versioned(payload, expectedVersion))
  ).data,
  update: async (id, payload, expectedVersion) => (
    await apiClient.put(`/columns/${id}`, versioned(payload, expectedVersion))
  ).data,
  delete: async (id, expectedVersion) => (
    await apiClient.delete(`/columns/${id}`, {
      headers: expectedVersion == null ? {} : { 'If-Match': String(expectedVersion) },
    })
  ).data,
  archive: async (id) => (await apiClient.post(`/columns/${id}/archive`, {})).data,
  restore: async (id) => (await apiClient.post(`/columns/${id}/restore`, {})).data,
}
