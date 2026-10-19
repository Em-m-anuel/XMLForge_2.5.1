import apiClient from './client'

function queryString({ limit = 25, offset = 0, search = '', sort = '', order = 'ASC', filters = {} }: any = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (search) params.set('search', search)
  if (sort) params.set('sort', sort)
  if (order) params.set('order', order)
  if (filters && Object.keys(filters).length) params.set('filters', JSON.stringify(filters))
  return params.toString()
}

export type Row = {
  id: number
  uuid: string
  table_id: number
  data: Record<string, any>
  created_at?: string | null
  updated_at?: string | null
}

export type RowsResponse = {
  rows: Row[]
  total: number
  limit: number
  offset: number
  table?: any
}

export const rowService = {
  list: async (tableId: number | string, options: any = {}): Promise<RowsResponse> => {
    const res = await apiClient.get(`/tables/${tableId}/rows?${queryString(options)}`)
    return res.data as RowsResponse
  },
  create: async (tableId: number | string, data: Record<string, any>, expectedVersion?: any): Promise<Row> => {
    const res = await apiClient.post(`/tables/${tableId}/rows`, {
      data,
      ...(expectedVersion == null ? {} : { expected_version: expectedVersion }),
    })
    return res.data as Row
  },
  update: async (tableId: number | string, rowId: number | string, data: Record<string, any>, expectedVersion?: any): Promise<Row> => {
    const res = await apiClient.put(`/tables/${tableId}/rows/${rowId}`, {
      data,
      ...(expectedVersion == null ? {} : { expected_version: expectedVersion }),
    })
    return res.data as Row
  },
  delete: async (tableId: number | string, rowId: number | string, expectedVersion?: any): Promise<void> => {
    await apiClient.delete(`/tables/${tableId}/rows/${rowId}`, {
      headers: expectedVersion == null ? {} : { 'If-Match': String(expectedVersion) },
    })
  },
}
