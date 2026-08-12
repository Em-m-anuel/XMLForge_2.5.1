import apiClient from './api'

export const databaseService = {
  list: async (includeArchived = true) => {
    const res = await apiClient.get(`/databases?include_archived=${includeArchived}`)
    return res.data
  },

  get: async (id) => {
    const res = await apiClient.get(`/databases/${id}`)
    return res.data
  },

  create: async ({ name, description }) => {
    const res = await apiClient.post('/databases', { name, description })
    return res.data
  },

  update: async (id, payload) => {
    const res = await apiClient.put(`/databases/${id}`, payload)
    return res.data
  },

  delete: async (id) => {
    const res = await apiClient.delete(`/databases/${id}`)
    return res.data
  },

  archive: async (id) => {
    const res = await apiClient.post(`/databases/${id}/archive`)
    return res.data
  },

  restore: async (id) => {
    const res = await apiClient.post(`/databases/${id}/restore`)
    return res.data
  },

  createReal: async (databaseId, targetName) => {
    const res = await apiClient.post('/database/create', { database_id: databaseId, target_database_name: targetName })
    return res.data
  }
}
