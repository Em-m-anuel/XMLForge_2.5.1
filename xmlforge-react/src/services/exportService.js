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
      // Pour download, on a besoin de fetch brut avec blob
      const token = localStorage.getItem('xmlforge_token')
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/export/xml/${databaseId}?download=true`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Erreur export XML')
      const blob = await res.blob()
      downloadBlob(blob, `database_${databaseId}.xml`)
      return { downloaded: true }
    } else {
      const res = await apiClient.get(`/export/xml/${databaseId}`)
      return res.data // {xml, database_id}
    }
  },

  exportSql: async (databaseId, { download = false } = {}) => {
    if (download) {
      const token = localStorage.getItem('xmlforge_token')
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/export/sql/${databaseId}?download=true`, {
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
}
