import apiClient from './client'

export const auditService = {
  list: async (limit = 100): Promise<any[]> => {
    const res = await apiClient.get(`/audit-logs?limit=${limit}`)
    return res.data as any[]
  },
}
