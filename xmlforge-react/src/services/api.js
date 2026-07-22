/**
 * Client API centralisé XMLForge
 * - Gestion automatique JWT
 * - Gestion X-Database-Key (session uniquement)
 * - Gestion erreurs 401/403/500
 * - Aucun composant ne doit appeler fetch directement
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

function getToken() {
  return localStorage.getItem('xmlforge_token')
}

function getDbKey() {
  // Clé conservée uniquement pendant la session (spec)
  return sessionStorage.getItem('xmlforge_db_key')
}

function setDbKey(key) {
  if (key) sessionStorage.setItem('xmlforge_db_key', key)
  else sessionStorage.removeItem('xmlforge_db_key')
}

async function parseResponse(res) {
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const err = new Error(data.message || `Erreur ${res.status}`)
      err.status = res.status
      err.data = data
      throw err
    }
    return data
  } else {
    // blob pour downloads
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      const err = new Error(text || `Erreur ${res.status}`)
      err.status = res.status
      throw err
    }
    return res
  }
}

async function request(path, { method = 'GET', body, isFormData = false, withAuth = true, withDbKey = true, ...customHeaders } = {}) {
  const url = path.startsWith('http') ? path : `${API_URL}${path.startsWith('/') ? '' : '/'}${path}`
  const headers = {}

  if (!isFormData) {
    headers['Content-Type'] = 'application/json'
  }

  if (withAuth) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  if (withDbKey) {
    const dbKey = getDbKey()
    if (dbKey) headers['X-Database-Key'] = dbKey
  }

  Object.assign(headers, customHeaders)

  const options = { method, headers }

  if (body) {
    options.body = isFormData ? body : JSON.stringify(body)
  }

  try {
    const res = await fetch(url, options)

    // Token expiré -> retour login
    if (res.status === 401) {
      localStorage.removeItem('xmlforge_token')
      localStorage.removeItem('xmlforge_user')
      sessionStorage.removeItem('xmlforge_db_key')
      // Éviter boucle infinie si on est déjà sur login
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
      const data = await res.json().catch(() => ({}))
      const err = new Error(data.message || 'Session expirée, veuillez vous reconnecter')
      err.status = 401
      throw err
    }

    return await parseResponse(res)
  } catch (err) {
    // Erreurs réseau ou autres
    if (err.status === 403) {
      // Optionnel: toast spécifique géré par appelant
    }
    throw err
  }
}

export const apiClient = {
  get: (path, opts) => request(path, { ...opts, method: 'GET' }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body, isFormData: body instanceof FormData }),
  put: (path, body, opts) => request(path, { ...opts, method: 'PUT', body }),
  delete: (path, opts) => request(path, { ...opts, method: 'DELETE' }),
  setDbKey,
  getDbKey,
  clearDbKey: () => setDbKey(null),
  getToken,
}

export default apiClient
