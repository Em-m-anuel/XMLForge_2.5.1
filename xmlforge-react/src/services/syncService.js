import apiClient from './api'

export const syncService = {
  syncDatabase: async (databaseId, xml, key) => {
    const body = { xml }
    if (key) body.key_identifier = key
    const res = await apiClient.post(`/databases/${databaseId}/sync-xml`, body)
    return res.data // {database, created_tables, updated_tables, created_columns, updated_columns, deleted_columns, details, sql}
  },

  syncDatabaseAlias: async (databaseId, xml, key) => {
    const body = { xml }
    if (key) body.key_identifier = key
    const res = await apiClient.post(`/databases/${databaseId}/sync`, body)
    return res.data
  }
}
