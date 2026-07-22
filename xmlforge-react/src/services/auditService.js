import apiClient from './api'

export const auditService = {
  list: async (limit = 100) => {
    const res = await apiClient.get(`/audit-logs?limit=${limit}`)
    return res.data
  },
}
