import apiClient from './client'

function withVersion(payload: any = {}, expectedVersion: any) {
  return expectedVersion == null ? payload : { ...payload, expected_version: expectedVersion }
}

export type Database = {
  id: number
  uuid: string
  name: string
  description: string
  creator_id: number
  creator_name: string
  owner_id: number
  owner_name: string
  scope: 'PERSONAL' | 'COMMON'
  common_permission: 'VIEW' | 'EDIT' | 'MANAGE' | null
  document_version: number
  sync_status: string
  created_at: string
  updated_at: string
  last_modified_by_id: number
  last_modified_by: string
  comment: string
  status: 'ACTIVE' | 'ARCHIVED'
  tables_count: number
  key_identifier?: string
  access?: {
    can_read: boolean
    can_write: boolean
    can_ddl: boolean
    can_admin: boolean
    level: 'VIEW' | 'EDIT' | 'MANAGE' | 'OWNER' | 'NONE'
  }
  is_owner?: boolean
}

export const databaseService = {
  list: async (includeArchived = true): Promise<Database[]> => {
    const res = await apiClient.get(`/databases?include_archived=${includeArchived}`)
    return res.data as Database[]
  },
  get: async (id: number | string): Promise<Database> => {
    const res = await apiClient.get(`/databases/${id}`)
    return res.data as Database
  },
  create: async (payload: { name: string; description?: string; comment?: string; scope?: 'PERSONAL' | 'COMMON'; common_permission?: 'VIEW' | 'EDIT' | 'MANAGE' | null }): Promise<Database> => {
    const res = await apiClient.post('/databases', payload)
    return res.data as Database
  },
  update: async (id: number | string, payload: any, expectedVersion?: number | string): Promise<Database> => {
    const res = await apiClient.put(`/databases/${id}`, withVersion(payload, expectedVersion))
    return res.data as Database
  },
  delete: async (id: number | string): Promise<void> => {
    await apiClient.delete(`/databases/${id}`)
  },
  archive: async (id: number | string): Promise<Database> => {
    const res = await apiClient.post(`/databases/${id}/archive`, {})
    return res.data as Database
  },
  restore: async (id: number | string): Promise<Database> => {
    const res = await apiClient.post(`/databases/${id}/restore`, {})
    return res.data as Database
  },
}
