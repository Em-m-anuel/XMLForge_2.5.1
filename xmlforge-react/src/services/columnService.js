import apiClient from './api'

export const columnService = {
  list: async (tableId, includeArchived = true) => {
    const res = await apiClient.get(`/columns/${tableId}?include_archived=${includeArchived}`)
    return res.data
  },

  create: async (payload, key) => {
    const body = { ...payload }
    if (key) body.key_identifier = key
    const res = await apiClient.post('/columns', body)
    return res.data
  },

  update: async (id, payload, key) => {
    const body = { ...payload }
    if (key) body.key_identifier = key
    const res = await apiClient.put(`/columns/${id}`, body)
    return res.data
  },

  delete: async (id, key) => {
    const headers = {}
    if (key) headers['X-Database-Key'] = key
    const query = key ? `?key=${encodeURIComponent(key)}` : ''
    const res = await apiClient.delete(`/columns/${id}${query}`, { ...headers })
    return res.data
  },

  archive: async (id, key) => {
    const body = key ? { key_identifier: key } : {}
    const res = await apiClient.post(`/columns/${id}/archive`, body)
    return res.data
  },

  restore: async (id, key) => {
    const body = key ? { key_identifier: key } : {}
    const res = await apiClient.post(`/columns/${id}/restore`, body)
    return res.data
  },

  getComment: async (id) => {
    const res = await apiClient.get(`/columns/${id}/comment`)
    return res.data
  },

  updateComment: async (id, comment, key) => {
    const res = await apiClient.put(`/columns/${id}/comment`, { comment, key_identifier: key })
    return res.data
  },
}
