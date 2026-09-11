import apiClient from './api'

const versioned = (payload = {}, expectedVersion) => expectedVersion == null ? payload : { ...payload, expected_version: expectedVersion }

export const tableService = {
  list: async (databaseId, includeArchived = true) => (
    await apiClient.get(`/tables/${databaseId}?include_archived=${includeArchived}`)
  ).data,
  get: async (tableId) => (await apiClient.get(`/tables/${tableId}/detail`)).data,
  create: async (payload, expectedVersion) => (
    await apiClient.post('/tables', versioned({
      ...payload,
      description: payload.description || '',
      is_protected: Boolean(payload.is_protected),
      file_identifier: payload.file_identifier || null,
    }, expectedVersion))
  ).data,
  update: async (id, payload, expectedVersion) => (
    await apiClient.put(`/tables/${id}`, versioned(payload, expectedVersion))
  ).data,
  delete: async (id, expectedVersion) => (
    await apiClient.delete(`/tables/${id}`, {
      headers: expectedVersion == null ? {} : { 'If-Match': String(expectedVersion) },
    })
  ).data,
  archive: async (id) => (await apiClient.post(`/tables/${id}/archive`, {})).data,
  restore: async (id) => (await apiClient.post(`/tables/${id}/restore`, {})).data,
  unlock: async (tableId, key) => (
    await apiClient.post('/unlock-table', { table_id: tableId, key_identifier: key })
  ).data,
  getXml: async (tableId) => (await apiClient.get(`/export/table-xml/${tableId}`)).data,
  getSql: async (tableId) => (await apiClient.get(`/export/table-sql/${tableId}`)).data,
  syncXml: async (tableId, xml, expectedVersion) => (
    await apiClient.post(`/tables/${tableId}/sync-xml`, { xml, expected_version: expectedVersion })
  ).data,
}
