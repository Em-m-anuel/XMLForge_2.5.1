import apiClient from './client'

export const userService = {
  list: async (search = ''): Promise<any[]> => {
    const res = await apiClient.get(`/users?search=${encodeURIComponent(search)}&include_inactive=true`)
    return res.data as any[]
  },
  get: async (id: number | string): Promise<any> => {
    const res = await apiClient.get(`/users/${id}`)
    return res.data as any
  },
  create: async (payload: { full_name: string; email: string; password: string; is_active?: boolean; role?: string }): Promise<any> => {
    const res = await apiClient.post('/users', payload)
    return res.data as any
  },
  update: async (id: number | string, payload: any): Promise<any> => {
    const res = await apiClient.put(`/users/${id}`, payload)
    return res.data as any
  },
  delete: async (id: number | string): Promise<void> => {
    await apiClient.delete(`/users/${id}`)
  },
  resetPassword: async (id: number | string, new_password: string): Promise<any> => {
    const res = await apiClient.post(`/users/${id}/reset-password`, { new_password })
    return res.data as any
  },
  toggleActive: async (id: number | string): Promise<any> => {
    const res = await apiClient.post(`/users/${id}/toggle-active`, {})
    return res.data as any
  },
}
