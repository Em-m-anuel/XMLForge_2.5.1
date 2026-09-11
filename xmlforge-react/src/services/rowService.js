import apiClient from './api'

function queryString({ limit = 25, offset = 0, search = '', sort = '', order = 'ASC', filters = {} } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (search) params.set('search', search)
  if (sort) params.set('sort', sort)
  if (order) params.set('order', order)
  if (filters && Object.keys(filters).length) params.set('filters', JSON.stringify(filters))
  return params.toString()
}

export const rowService = {
  list: async (tableId, options) => (
    await apiClient.get(`/tables/${tableId}/rows?${queryString(options)}`)
  ).data,
  create: async (tableId, data, expectedVersion) => (
    await apiClient.post(`/tables/${tableId}/rows`, {
      data,
      ...(expectedVersion == null ? {} : { expected_version: expectedVersion }),
    })
  ).data,
  update: async (tableId, rowId, data, expectedVersion) => (
    await apiClient.put(`/tables/${tableId}/rows/${rowId}`, {
      data,
      ...(expectedVersion == null ? {} : { expected_version: expectedVersion }),
    })
  ).data,
  delete: async (tableId, rowId, expectedVersion) => (
    await apiClient.delete(`/tables/${tableId}/rows/${rowId}`, {
      headers: expectedVersion == null ? {} : { 'If-Match': String(expectedVersion) },
    })
  ).data,
}
