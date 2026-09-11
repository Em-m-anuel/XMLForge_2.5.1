import apiClient from './api'

export const authService = {
  register: async ({ full_name, email, password }) => {
    const res = await apiClient.post('/register', { full_name, email, password }, { withAuth: false })
    return res.data
  },

  login: async ({ email, password }) => {
    const res = await apiClient.post('/login', { email, password }, { withAuth: false })
    const { access_token, user } = res.data || {}
    if (access_token) {
      localStorage.setItem('xmlforge_token', access_token)
      localStorage.setItem('xmlforge_user', JSON.stringify(user))
    }
    return res.data
  },

  me: async () => {
    const res = await apiClient.get('/me')
    return res.data
  },

  logout: async () => {
    try {
      await apiClient.post('/logout')
    } catch {
      // même si échec, on nettoie côté client
    } finally {
      localStorage.removeItem('xmlforge_token')
      localStorage.removeItem('xmlforge_user')
      sessionStorage.removeItem('xmlforge_unlocks')
    }
  },

  getStoredUser: () => {
    try {
      return JSON.parse(localStorage.getItem('xmlforge_user') || 'null')
    } catch {
      return null
    }
  },

  isAuthenticated: () => !!localStorage.getItem('xmlforge_token'),
}
