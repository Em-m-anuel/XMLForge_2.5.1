import apiClient from './client'

export const serverService = {
  health: async (): Promise<any> => {
    const res = await apiClient.get('/health', { withAuth: false })
    return res as any
  },
  // Ancienne route rebuild-projection conservée no-op XML_ONLY
  rebuildProjection: async (databaseId: number | string): Promise<any> => {
    const res = await apiClient.post(`/databases/${databaseId}/rebuild-projection`, {})
    return res.data as any
  },
  shutdown: async (): Promise<any> => {
    const res = await apiClient.post('/shutdown', {})
    return res as any
  },
}
