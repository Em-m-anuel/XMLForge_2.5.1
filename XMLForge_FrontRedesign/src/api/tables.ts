import apiClient from './client'

function withVersion(payload: any = {}, expectedVersion: any) {
  return expectedVersion == null ? payload : { ...payload, expected_version: expectedVersion }
}

export type Table = {
  id: number
  uuid: string
  name: string
  description: string
  database_id: number
  creator_id: number
  creator_name: string
  created_at: string
  updated_at: string
  last_modified_by_id?: number
  last_modified_by?: string
  comment: string
  status: 'ACTIVE' | 'ARCHIVED'
  is_protected: boolean
  has_file_identifier: boolean
  protected: boolean
  archived: boolean
  columns_count: number
  file_identifier?: string
  access?: {
    can_read: boolean
    can_write: boolean
    can_ddl: boolean
    can_admin: boolean
    level: string
  }
}

export const tableService = {
  list: async (databaseId: number | string, includeArchived = true): Promise<Table[]> => {
    const res = await apiClient.get(`/tables/${databaseId}?include_archived=${includeArchived}`)
    return res.data as Table[]
  },
  get: async (tableId: number | string): Promise<Table> => {
    const res = await apiClient.get(`/tables/${tableId}/detail`)
    return res.data as Table
  },
  create: async (payload: { name: string; database_id: number; description?: string; is_protected?: boolean; file_identifier?: string | null; comment?: string }, expectedVersion?: any): Promise<Table> => {
    const res = await apiClient.post('/tables', withVersion({
      ...payload,
      description: payload.description || '',
      is_protected: Boolean(payload.is_protected),
      file_identifier: payload.file_identifier || null,
    }, expectedVersion))
    return res.data as Table
  },
  update: async (id: number | string, payload: any, expectedVersion?: any): Promise<Table> => {
    const res = await apiClient.put(`/tables/${id}`, withVersion(payload, expectedVersion))
    return res.data as Table
  },
  delete: async (id: number | string, expectedVersion?: any): Promise<void> => {
    await apiClient.delete(`/tables/${id}`, {
      headers: expectedVersion == null ? {} : { 'If-Match': String(expectedVersion) },
    })
  },
  archive: async (id: number | string): Promise<Table> => {
    const res = await apiClient.post(`/tables/${id}/archive`, {})
    return res.data as Table
  },
  restore: async (id: number | string): Promise<Table> => {
    const res = await apiClient.post(`/tables/${id}/restore`, {})
    return res.data as Table
  },
  unlock: async (tableId: number | string, key: string): Promise<any> => {
    const res = await apiClient.post('/unlock-table', { table_id: tableId, key_identifier: key })
    return res.data
  },
  getXml: async (tableId: number | string): Promise<{ xml: string; document_version?: number }> => {
    const res = await apiClient.get(`/export/table-xml/${tableId}`)
    return res.data as any
  },
  getSql: async (tableId: number | string): Promise<{ sql: string }> => {
    const res = await apiClient.get(`/export/table-sql/${tableId}`)
    return res.data as any
  },
  syncXml: async (tableId: number | string, xml: string, expectedVersion?: any): Promise<any> => {
    const res = await apiClient.post(`/tables/${tableId}/sync-xml`, { xml, expected_version: expectedVersion })
    return res.data as any
  },
}
