import apiClient from './api'

export const tcpService = {
  credentials: async () => (await apiClient.get('/tcp/credentials')).data,
  create: async (payload = {}) => (await apiClient.post('/tcp/credentials', payload)).data,
  update: async (payload) => (await apiClient.put('/tcp/credentials', payload)).data,
  regenerate: async () => (await apiClient.post('/tcp/credentials/regenerate', {})).data,
  reveal: async (currentPassword) => (
    await apiClient.post('/tcp/credentials/show-password', { current_password: currentPassword })
  ).data,
  remove: async () => (await apiClient.delete('/tcp/credentials')).data,
  sessions: async () => (await apiClient.get('/tcp/sessions')).data,
  status: async () => (await apiClient.get('/tcp/status', { withAuth: false })).data,
}
