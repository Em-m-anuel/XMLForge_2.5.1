import apiClient from './api'

export const historyService = {
  list: async (limit = 100, databaseId = null) => {
    let url = `/history?limit=${limit}`
    if (databaseId) url += `&database_id=${databaseId}`
    const res = await apiClient.get(url)
    return res.data
  },
}
