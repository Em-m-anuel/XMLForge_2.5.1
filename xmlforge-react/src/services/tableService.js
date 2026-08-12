import apiClient from './api'

export const tableService = {
  list: async (databaseId, includeArchived = true) => {
    const res = await apiClient.get(`/tables/${databaseId}?include_archived=${includeArchived}`)
    return res.data
  },

  create: async ({ name, description, database_id, is_protected, file_identifier }) => {
    const body = {
      name,
      description: description || '',
      database_id,
      is_protected: !!is_protected,
      file_identifier: file_identifier || null,
    }
    const res = await apiClient.post('/tables', body)
    return res.data
  },

  update: async (id, payload, key) => {
    const body = { ...payload }
    if (key) body.key_identifier = key
    const res = await apiClient.put(`/tables/${id}`, body)
    return res.data
  },

  delete: async (id, key) => {
    const headers = {}
    if (key) headers['X-Database-Key'] = key
    const query = key ? `?key=${encodeURIComponent(key)}` : ''
    const res = await apiClient.delete(`/tables/${id}${query}`, { ...headers })
    return res.data
  },

  archive: async (id, key) => {
    const body = key ? { key_identifier: key } : {}
    const res = await apiClient.post(`/tables/${id}/archive`, body)
    return res.data
  },

  restore: async (id, key) => {
    const body = key ? { key_identifier: key } : {}
    const res = await apiClient.post(`/tables/${id}/restore`, body)
    return res.data
  },

  unlock: async (tableId, key) => {
    const res = await apiClient.post('/unlock-table', { table_id: tableId, key_identifier: key })
    if (res.data?.unlocked) {
      apiClient.setDbKey(key)
    }
    return res.data
  },

  // NEW V4: XML per table
  getXml: async (tableId) => {
    const res = await apiClient.get(`/export/table-xml/${tableId}`)
    return res.data // {xml, table_id}
  },

  getSql: async (tableId) => {
    const res = await apiClient.get(`/export/table-sql/${tableId}`)
    return res.data // {sql, table_id}
  },

  syncXml: async (tableId, xml, key) => {
    const body = { xml }
    if (key) body.key_identifier = key
    const res = await apiClient.post(`/tables/${tableId}/sync-xml`, body)
    return res.data
  },

  exportXmlDownload: async (tableId) => {
    const token = localStorage.getItem('xmlforge_token')
    const base = import.meta.env.VITE_API_URL || 'http://localhost:5000'
    const res = await fetch(`${base}/export/table-xml/${tableId}?download=true`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!res.ok) throw new Error('Erreur export XML table')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `table_${tableId}.xml`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    return { downloaded: true }
  },

  exportSqlDownload: async (tableId) => {
    const token = localStorage.getItem('xmlforge_token')
    const base = import.meta.env.VITE_API_URL || 'http://localhost:5000'
    const res = await fetch(`${base}/export/table-sql/${tableId}?download=true`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!res.ok) throw new Error('Erreur export SQL table')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `table_${tableId}.sql`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    return { downloaded: true }
  }
}
