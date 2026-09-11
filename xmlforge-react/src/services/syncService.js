import apiClient from './api'

export const syncService = {
  syncDatabase: async (databaseId, xml, expectedVersion) => (
    await apiClient.post(`/databases/${databaseId}/sync-xml`, {
      xml,
      expected_version: expectedVersion,
    })
  ).data,
  syncTable: async (tableId, xml, expectedVersion) => (
    await apiClient.post(`/tables/${tableId}/sync-xml`, {
      xml,
      expected_version: expectedVersion,
    })
  ).data,
}
