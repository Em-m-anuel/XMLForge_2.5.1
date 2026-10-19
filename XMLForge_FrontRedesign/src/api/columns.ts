import apiClient from './client'

function versioned(payload: any = {}, expectedVersion: any) {
  return expectedVersion == null ? payload : { ...payload, expected_version: expectedVersion }
}

export type Column = {
  id: number
  uuid: string
  name: string
  type: string
  length: string
  nullable: boolean
  primary_key: boolean
  foreign_key: boolean
  unique: boolean
  auto_increment: boolean
  default: any
  references: string | null
  on_delete: string
  on_update: string
  index: boolean
  comment: string
  status: 'ACTIVE' | 'ARCHIVED'
  table_id: number
}

export const columnService = {
  list: async (tableId: number | string, includeArchived = true): Promise<Column[]> => {
    const res = await apiClient.get(`/columns/${tableId}?include_archived=${includeArchived}`)
    return res.data as Column[]
  },
  get: async (columnId: number | string): Promise<Column> => {
    const res = await apiClient.get(`/columns/${columnId}/detail`)
    return res.data as Column
  },
  create: async (payload: any, expectedVersion?: any): Promise<Column> => {
    const res = await apiClient.post('/columns', versioned(payload, expectedVersion))
    return res.data as Column
  },
  update: async (id: number | string, payload: any, expectedVersion?: any): Promise<Column> => {
    const res = await apiClient.put(`/columns/${id}`, versioned(payload, expectedVersion))
    return res.data as Column
  },
  delete: async (id: number | string, expectedVersion?: any): Promise<void> => {
    await apiClient.delete(`/columns/${id}`, {
      headers: expectedVersion == null ? {} : { 'If-Match': String(expectedVersion) },
    })
  },
  archive: async (id: number | string): Promise<Column> => {
    const res = await apiClient.post(`/columns/${id}/archive`, {})
    return res.data as Column
  },
  restore: async (id: number | string): Promise<Column> => {
    const res = await apiClient.post(`/columns/${id}/restore`, {})
    return res.data as Column
  },
}
