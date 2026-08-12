import apiClient from './api'

export const syncService = {
  syncDatabase: async (databaseId, xml, key) => {
    const body = { xml }
    if (key) body.key_identifier = key
    const res = await apiClient.post(`/databases/${databaseId}/sync-xml`, body)
    return res.data
  },

  syncDatabaseAlias: async (databaseId, xml, key) => {
    const body = { xml }
    if (key) body.key_identifier = key
    const res = await apiClient.post(`/databases/${databaseId}/sync`, body)
    return res.data
  },

  // V4: sync per table
  syncTable: async (tableId, xml, key) => {
    const body = { xml }
    if (key) body.key_identifier = key
    const res = await apiClient.post(`/tables/${tableId}/sync-xml`, body)
    return res.data
  },

  syncTableAlias: async (tableId, xml, key) => {
    const body = { xml }
    if (key) body.key_identifier = key
    const res = await apiClient.post(`/tables/${tableId}/sync`, body)
    return res.data
  }
}
