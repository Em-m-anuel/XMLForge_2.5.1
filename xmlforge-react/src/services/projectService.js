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

export const projectService = {
  exportProject: async (databaseId, { download = false } = {}) => {
    if (download) {
      const token = localStorage.getItem('xmlforge_token')
      const base = import.meta.env.VITE_API_URL || 'http://localhost:5000'
      const res = await fetch(`${base}/export/project/${databaseId}?download=true`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Erreur export projet')
      const blob = await res.blob()
      downloadBlob(blob, `project_${databaseId}.xml`)
      return { downloaded: true }
    } else {
      const res = await apiClient.get(`/export/project/${databaseId}`)
      return res.data
    }
  },

  exportProjectXml: async (databaseId) => {
    const res = await apiClient.get(`/export/project/${databaseId}`)
    return res.data
  },

  importProject: async (fileOrXml) => {
    if (fileOrXml instanceof File) {
      const form = new FormData()
      form.append('file', fileOrXml)
      const res = await apiClient.post('/import/project', form)
      return res.data
    } else {
      const res = await apiClient.post('/import/project', { xml: fileOrXml })
      return res.data
    }
  }
}
