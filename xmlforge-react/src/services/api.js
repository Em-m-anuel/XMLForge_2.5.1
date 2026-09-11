const configuredApiUrl = (import.meta.env.VITE_API_URL || '/api').trim()
const API_URL = configuredApiUrl.replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status, payload = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
    this.code = payload?.errors?.code || payload?.code || null
    this.details = payload?.errors?.details || payload?.errors || null
    this.isConflict = status === 409
  }
}

function getToken() {
  return localStorage.getItem('xmlforge_token')
}

function decodeToken(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(decodeURIComponent(atob(payload).split('').map(char => `%${(`00${char.charCodeAt(0).toString(16)}`).slice(-2)}`).join('')))
  } catch {
    return null
  }
}

function isTokenExpired(token = getToken()) {
  if (!token) return true
  const payload = decodeToken(token)
  return !payload?.exp || payload.exp * 1000 <= Date.now()
}

function clearSession(reason = 'expired') {
  localStorage.removeItem('xmlforge_token')
  localStorage.removeItem('xmlforge_user')
  sessionStorage.removeItem('xmlforge_unlocks')
  window.dispatchEvent(new CustomEvent('xmlforge:unauthorized', { detail: { reason } }))
}

function buildUrl(path) {
  if (/^https?:\/\//i.test(path)) return path
  return `${API_URL}${path.startsWith('/') ? path : `/${path}`}`
}

function friendlyMessage(status, payload) {
  if (payload?.message) return payload.message
  if (status === 401) return 'Session expirée. Veuillez vous reconnecter.'
  if (status === 403) return 'Vous ne disposez pas des droits nécessaires.'
  if (status === 404) return 'La ressource demandée est introuvable.'
  if (status === 409) return 'Cette base a été modifiée depuis votre dernière synchronisation.'
  if (status === 400 || status === 422) return 'Les données envoyées sont invalides.'
  if (status >= 500) return 'Le serveur XMLForge a rencontré une erreur.'
  return `Erreur HTTP ${status}`
}

async function parseError(response) {
  const contentType = response.headers.get('content-type') || ''
  let payload = null
  if (contentType.includes('application/json')) {
    payload = await response.json().catch(() => null)
  } else {
    const text = await response.text().catch(() => '')
    payload = text ? { message: text } : null
  }
  return new ApiError(friendlyMessage(response.status, payload), response.status, payload)
}

async function request(path, {
  method = 'GET',
  body,
  withAuth = true,
  headers: customHeaders = {},
  signal,
  responseType = 'json',
} = {}) {
  const token = getToken()
  if (withAuth && token && isTokenExpired(token)) {
    clearSession('expired')
    throw new ApiError('Session expirée. Veuillez vous reconnecter.', 401)
  }

  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  const headers = { Accept: responseType === 'blob' ? '*/*' : 'application/json', ...customHeaders }
  if (!isFormData && body !== undefined) headers['Content-Type'] = 'application/json'
  if (withAuth && token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(buildUrl(path), {
      method,
      headers,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('Impossible de joindre le backend XMLForge.', 0, { cause: error.message })
  }

  if (response.status === 401 && withAuth) clearSession('unauthorized')
  if (!response.ok) throw await parseError(response)
  if (responseType === 'blob') return response.blob()
  if (response.status === 204) return null
  return response.json()
}

function downloadBlob(blob, filename) {
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}

export const apiClient = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' }),
  blob: (path, options) => request(path, { ...options, method: 'GET', responseType: 'blob' }),
  download: async (path, filename, options) => {
    const blob = await request(path, { ...options, method: 'GET', responseType: 'blob' })
    downloadBlob(blob, filename)
    return { downloaded: true }
  },
  getToken,
  isTokenExpired,
  clearSession,
  apiUrl: API_URL,
}

export function getSocketUrl() {
  if (import.meta.env.VITE_SOCKET_URL) return import.meta.env.VITE_SOCKET_URL.replace(/\/$/, '')
  if (/^https?:\/\//i.test(API_URL)) return API_URL.replace(/\/api$/, '')
  return window.location.origin
}

export default apiClient
