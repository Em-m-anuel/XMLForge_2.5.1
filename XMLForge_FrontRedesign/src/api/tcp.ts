import apiClient from './client'

export const tcpService = {
  credentials: async (): Promise<any> => {
    const res = await apiClient.get('/tcp/credentials')
    return res.data as any
  },
  create: async (payload: any = {}): Promise<any> => {
    const res = await apiClient.post('/tcp/credentials', payload)
    return res.data as any
  },
  update: async (payload: any): Promise<any> => {
    const res = await apiClient.put('/tcp/credentials', payload)
    return res.data as any
  },
  regenerate: async (): Promise<any> => {
    const res = await apiClient.post('/tcp/credentials/regenerate', {})
    return res.data as any
  },
  reveal: async (currentPassword: string): Promise<any> => {
    const res = await apiClient.post('/tcp/credentials/show-password', { current_password: currentPassword })
    return res.data as any
  },
  remove: async (): Promise<void> => {
    await apiClient.delete('/tcp/credentials')
  },
  sessions: async (): Promise<any[]> => {
    const res = await apiClient.get('/tcp/sessions')
    return res.data as any[]
  },
  status: async (): Promise<any> => {
    const res = await apiClient.get('/tcp/status', { withAuth: false })
    return res.data as any
  },
}
