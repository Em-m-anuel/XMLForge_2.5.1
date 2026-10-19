import apiClient from './client'

export type QueryResult = {
  rows?: any[]
  columns?: string[]
  total?: number
  count?: number
  inserted?: number
  updated?: number
  deleted?: number
  created?: string
  dropped?: string
  table?: any
  timing?: { ms: number }
  [key: string]: any
}

export const queryService = {
  execute: async (databaseId: number | string, sql: string, expectedVersion?: any): Promise<QueryResult> => {
    const res = await apiClient.post(`/databases/${databaseId}/query`, {
      sql,
      expected_version: expectedVersion,
    })
    return res.data as QueryResult
  },
  schema: async (databaseId: number | string): Promise<any> => {
    const res = await apiClient.get(`/databases/${databaseId}/schema`)
    return res.data
  },
}
