import apiClient from './client'

export const xmlService = {
  exportDatabaseXml: async (databaseId: number | string): Promise<{ xml: string; document_version?: number }> => {
    const res = await apiClient.get(`/export/xml/${databaseId}`)
    return res.data as any
  },
  exportDatabaseSql: async (databaseId: number | string): Promise<{ sql: string }> => {
    const res = await apiClient.get(`/export/sql/${databaseId}`)
    return res.data as any
  },
  exportTableXml: async (tableId: number | string): Promise<{ xml: string; document_version?: number }> => {
    const res = await apiClient.get(`/export/table-xml/${tableId}`)
    return res.data as any
  },
  exportTableSql: async (tableId: number | string): Promise<{ sql: string }> => {
    const res = await apiClient.get(`/export/table-sql/${tableId}`)
    return res.data as any
  },
  syncDatabase: async (databaseId: number | string, xml: string, expectedVersion?: any): Promise<any> => {
    const res = await apiClient.post(`/databases/${databaseId}/sync-xml`, { xml, expected_version: expectedVersion })
    return res.data as any
  },
  syncTable: async (tableId: number | string, xml: string, expectedVersion?: any): Promise<any> => {
    const res = await apiClient.post(`/tables/${tableId}/sync-xml`, { xml, expected_version: expectedVersion })
    return res.data as any
  },
  xmlToSql: async (xml: string, databaseName?: string): Promise<{ sql: string }> => {
    const res = await apiClient.post('/convert/xml-to-sql', { xml, database_name: databaseName })
    return res.data as any
  },
  sqlToXml: async (sql: string, databaseName?: string): Promise<{ xml: string }> => {
    const res = await apiClient.post('/convert/sql-to-xml', { sql, database_name: databaseName })
    return res.data as any
  },
  importXml: async (file: File): Promise<any> => {
    const form = new FormData()
    form.append('file', file)
    const res = await apiClient.post('/import/xml', form)
    return res.data as any
  },
  importXmlRaw: async (xml: string, name?: string): Promise<any> => {
    const res = await apiClient.post('/import/xml', { xml, name })
    return res.data as any
  },
  importSql: async (file: File): Promise<any> => {
    const form = new FormData()
    form.append('file', file)
    const res = await apiClient.post('/import/sql', form)
    return res.data as any
  },
  exportProject: async (databaseId: number | string, { download = false, name }: any = {}): Promise<any> => {
    if (download) {
      return apiClient.download(`/export/project/${databaseId}?download=true`, `${name || `database_${databaseId}`}_project.xml`)
    }
    const res = await apiClient.get(`/export/project/${databaseId}`)
    return res.data as any
  },
  importProject: async (file: File): Promise<any> => {
    const form = new FormData()
    form.append('file', file)
    const res = await apiClient.post('/import/project', form)
    return res.data as any
  },
}
