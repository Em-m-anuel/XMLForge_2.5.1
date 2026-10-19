import apiClient from './client'

export const historyService = {
  list: async (limit = 100, offset = 0): Promise<any[]> => {
    const res = await apiClient.get(`/history?limit=${limit}&offset=${offset}`)
    return res.data as any[]
  },
}
