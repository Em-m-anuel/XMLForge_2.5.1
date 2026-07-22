import apiClient from './api'

export const tableService = {
  list: async (databaseId, includeArchived = true) => {
    const res = await apiClient.get(`/tables/${databaseId}?include_archived=${includeArchived}`)
    return res.data
  },

  create: async ({ name, description, database_id, is_protected, comment }) => {
    const res = await apiClient.post('/tables', { name, description, database_id, is_protected, comment })
    return res.data
  },

  update: async (id, payload, key) => {
    // payload peut contenir name, description, is_protected, comment, key_identifier
    const body = { ...payload }
    if (key) body.key_identifier = key
    const res = await apiClient.put(`/tables/${id}`, body)
    return res.data
  },

  delete: async (id, key) => {
    const headers = {}
    if (key) headers['X-Database-Key'] = key
    const query = key ? `?key=${encodeURIComponent(key)}` : ''
    const res = await apiClient.delete(`/tables/${id}${query}`, { ...headers })
    return res.data
  },

  archive: async (id, key) => {
    const body = key ? { key_identifier: key } : {}
    const res = await apiClient.post(`/tables/${id}/archive`, body)
    return res.data
  },

  restore: async (id, key) => {
    const body = key ? { key_identifier: key } : {}
    const res = await apiClient.post(`/tables/${id}/restore`, body)
    return res.data
  },

  getComment: async (id) => {
    const res = await apiClient.get(`/tables/${id}/comment`)
    return res.data
  },

  updateComment: async (id, comment, key) => {
    const res = await apiClient.put(`/tables/${id}/comment`, { comment, key_identifier: key })
    return res.data
  },

  unlock: async (tableId, key) => {
    const res = await apiClient.post('/unlock-table', { table_id: tableId, key_identifier: key })
    if (res.data?.unlocked) {
      apiClient.setDbKey(key)
    }
    return res.data
  },
}
