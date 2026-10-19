import apiClient from './client'

export const permissionService = {
  listDatabase: async (databaseId: number | string): Promise<any[]> => {
    const res = await apiClient.get(`/databases/${databaseId}/permissions`)
    return res.data as any[]
  },
  grantDatabase: async (databaseId: number | string, payload: { email?: string; user_id?: number; can_read?: boolean; can_write?: boolean; can_ddl?: boolean; can_admin?: boolean }): Promise<any> => {
    const res = await apiClient.post(`/databases/${databaseId}/permissions`, payload)
    return res.data as any
  },
  revokeDatabase: async (databaseId: number | string, userId: number | string): Promise<void> => {
    await apiClient.delete(`/databases/${databaseId}/permissions/${userId}`)
  },
  listTable: async (tableId: number | string): Promise<any[]> => {
    const res = await apiClient.get(`/tables/${tableId}/permissions`)
    return res.data as any[]
  },
  grantTable: async (tableId: number | string, payload: any): Promise<any> => {
    const res = await apiClient.post(`/tables/${tableId}/permissions`, payload)
    return res.data as any
  },
  revokeTable: async (tableId: number | string, userId: number | string): Promise<void> => {
    await apiClient.delete(`/tables/${tableId}/permissions/${userId}`)
  },
}

export function accessLevel(entity: any): string {
  return entity?.access?.level || (entity?.is_owner ? 'MANAGE' : 'NONE')
}
