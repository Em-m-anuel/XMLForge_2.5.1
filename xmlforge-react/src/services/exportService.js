import apiClient from './api'

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const exportService = {
  exportXml: async (databaseId, { download = false } = {}) => {
    if (download) {
      const token = localStorage.getItem('xmlforge_token')
      const base = import.meta.env.VITE_API_URL || 'http://localhost:5000'
      const res = await fetch(`${base}/export/xml/${databaseId}?download=true`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Erreur export XML')
      const blob = await res.blob()
      downloadBlob(blob, `database_${databaseId}.xml`)
      return { downloaded: true }
    } else {
      const res = await apiClient.get(`/export/xml/${databaseId}`)
      return res.data
    }
  },

  exportSql: async (databaseId, { download = false } = {}) => {
    if (download) {
      const token = localStorage.getItem('xmlforge_token')
      const base = import.meta.env.VITE_API_URL || 'http://localhost:5000'
      const res = await fetch(`${base}/export/sql/${databaseId}?download=true`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Erreur export SQL')
      const blob = await res.blob()
      downloadBlob(blob, `database_${databaseId}.sql`)
      return { downloaded: true }
    } else {
      const res = await apiClient.get(`/export/sql/${databaseId}`)
      return res.data
    }
  },

  // Table exports (V4)
  exportTableXml: async (tableId, { download = false } = {}) => {
    if (download) {
      const token = localStorage.getItem('xmlforge_token')
      const base = import.meta.env.VITE_API_URL || 'http://localhost:5000'
      const res = await fetch(`${base}/export/table-xml/${tableId}?download=true`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Erreur export XML table')
      const blob = await res.blob()
      downloadBlob(blob, `table_${tableId}.xml`)
      return { downloaded: true }
    } else {
      const res = await apiClient.get(`/export/table-xml/${tableId}`)
      return res.data
    }
  },

  exportTableSql: async (tableId, { download = false } = {}) => {
    if (download) {
      const token = localStorage.getItem('xmlforge_token')
      const base = import.meta.env.VITE_API_URL || 'http://localhost:5000'
      const res = await fetch(`${base}/export/table-sql/${tableId}?download=true`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Erreur export SQL table')
      const blob = await res.blob()
      downloadBlob(blob, `table_${tableId}.sql`)
      return { downloaded: true }
    } else {
      const res = await apiClient.get(`/export/table-sql/${tableId}`)
      return res.data
    }
  }
}
