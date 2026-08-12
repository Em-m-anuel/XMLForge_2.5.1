import apiClient from './api'

export const unlockService = {
  unlock: async (tableId, key) => {
    const res = await apiClient.post('/unlock-table', { table_id: tableId, key_identifier: key })
    return res.data
  },

  list: async () => {
    const res = await apiClient.get('/unlocks')
    return res.data
  },

  clear: async () => {
    const res = await apiClient.delete('/unlocks')
    return res.data
  }
}
