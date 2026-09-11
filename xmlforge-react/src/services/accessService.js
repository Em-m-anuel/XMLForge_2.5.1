import apiClient from './api'

export const accessService = {
  listDatabase: async (databaseId) => (await apiClient.get(`/databases/${databaseId}/permissions`)).data,
  grantDatabase: async (databaseId, { email, userId, can_read, can_write, can_ddl, can_admin }) => (
    await apiClient.post(`/databases/${databaseId}/permissions`, {
      email: email || undefined,
      user_id: userId || undefined,
      can_read, can_write, can_ddl, can_admin,
    })
  ).data,
  revokeDatabase: async (databaseId, userId) => (
    await apiClient.delete(`/databases/${databaseId}/permissions/${userId}`)
  ).data,
  listTable: async (tableId) => (await apiClient.get(`/tables/${tableId}/permissions`)).data,
  grantTable: async (tableId, payload) => (await apiClient.post(`/tables/${tableId}/permissions`, payload)).data,
  revokeTable: async (tableId, userId) => (await apiClient.delete(`/tables/${tableId}/permissions/${userId}`)).data,
}

export function accessLevel(entity) {
  return entity?.access?.level || (entity?.is_owner ? 'MANAGE' : 'NONE')
}
