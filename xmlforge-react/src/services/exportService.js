import apiClient from './api'

export const exportService = {
  exportXml: async (databaseId, { download = false, name } = {}) => {
    if (download) return apiClient.download(`/export/xml/${databaseId}?download=true`, `${name || `database_${databaseId}`}.xml`)
    return (await apiClient.get(`/export/xml/${databaseId}`)).data
  },
  exportSql: async (databaseId, { download = false, name } = {}) => {
    if (download) return apiClient.download(`/export/sql/${databaseId}?download=true`, `${name || `database_${databaseId}`}.sql`)
    return (await apiClient.get(`/export/sql/${databaseId}`)).data
  },
  exportTableXml: async (tableId, { download = false, name } = {}) => {
    if (download) return apiClient.download(`/export/table-xml/${tableId}?download=true`, `${name || `table_${tableId}`}.xml`)
    return (await apiClient.get(`/export/table-xml/${tableId}`)).data
  },
  exportTableSql: async (tableId, { download = false, name } = {}) => {
    if (download) return apiClient.download(`/export/table-sql/${tableId}?download=true`, `${name || `table_${tableId}`}.sql`)
    return (await apiClient.get(`/export/table-sql/${tableId}`)).data
  },
}
