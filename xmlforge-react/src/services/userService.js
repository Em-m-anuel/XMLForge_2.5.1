import apiClient from './api'

export const userService = {
  list: async (search = '') => {
    const res = await apiClient.get(`/users?search=${encodeURIComponent(search)}&include_inactive=true`)
    return res.data
  },

  get: async (id) => {
    const res = await apiClient.get(`/users/${id}`)
    return res.data
  },

  create: async ({ full_name, email, password, is_active = true, role = 'user' }) => {
    const res = await apiClient.post('/users', { full_name, email, password, is_active, role })
    return res.data
  },

  update: async (id, payload) => {
    const res = await apiClient.put(`/users/${id}`, payload)
    return res.data
  },

  delete: async (id) => {
    const res = await apiClient.delete(`/users/${id}`)
    return res.data
  },

  resetPassword: async (id, new_password) => {
    const res = await apiClient.post(`/users/${id}/reset-password`, { new_password })
    return res.data
  },

  toggleActive: async (id) => {
    const res = await apiClient.post(`/users/${id}/toggle-active`)
    return res.data
  }
}
