import apiClient from './api'

export const rowService = {
  list: async (tableId, { limit = 200, offset = 0 } = {}) => {
    const res = await apiClient.get(`/tables/${tableId}/rows?limit=${limit}&offset=${offset}`)
    return res.data
  },

  create: async (tableId, data, key) => {
    const body = { data }
    if (key) body.key_identifier = key
    const res = await apiClient.post(`/tables/${tableId}/rows`, body)
    return res.data
  },

  update: async (tableId, rowId, data, key) => {
    const body = { data }
    if (key) body.key_identifier = key
    const res = await apiClient.put(`/tables/${tableId}/rows/${rowId}`, body)
    return res.data
  },

  delete: async (tableId, rowId, key) => {
    const query = key ? `?key=${encodeURIComponent(key)}` : ''
    const res = await apiClient.delete(`/tables/${tableId}/rows/${rowId}${query}`)
    return res.data
  }
}
