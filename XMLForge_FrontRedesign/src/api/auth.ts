/**
 * XMLForge Auth — API réelle
 * POST /register, POST /login, GET /me, POST /logout
 * JWT stocké dans localStorage xmlforge_token, user dans xmlforge_user
 */

import apiClient from './client'

export type AuthUser = {
  id: number
  full_name: string
  email: string
  role: string
  is_admin: boolean
  is_active: boolean
  created_at?: string
  initials?: string
}

type LoginResponse = {
  user: AuthUser
  access_token: string
}

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(p => p[0]!.toUpperCase())
    .join('') || '??'
}

export async function apiRegister(input: { name: string; email: string; password: string }): Promise<{ ok: true; user: any } | { ok: false; error: string }> {
  try {
    const res = await apiClient.post('/register', {
      full_name: input.name.trim(),
      email: input.email.trim(),
      password: input.password,
    }, { withAuth: false })
    // backend returns {success, data: user.to_dict()}
    return { ok: true, user: res.data }
  } catch (e: any) {
    return { ok: false, error: e.message || 'Erreur inscription' }
  }
}

export async function apiLogin(input: { email: string; password: string }): Promise<{ ok: true; user: AuthUser } | { ok: false; error: string }> {
  try {
    const res = await apiClient.post('/login', {
      email: input.email.trim(),
      password: input.password,
    }, { withAuth: false })
    const data = res.data as LoginResponse
    const user = data.user
    const token = data.access_token
    if (token) {
      localStorage.setItem('xmlforge_token', token)
      // enrichir avec initials pour UI
      const enriched = { ...user, initials: initialsOf(user.full_name || user.email) }
      localStorage.setItem('xmlforge_user', JSON.stringify(enriched))
      return { ok: true, user: enriched }
    }
    return { ok: false, error: 'Token manquant' }
  } catch (e: any) {
    return { ok: false, error: e.message || 'Erreur connexion' }
  }
}

export async function apiMe(): Promise<AuthUser | null> {
  try {
    const res = await apiClient.get('/me')
    const user = res.data as AuthUser
    const enriched = { ...user, initials: initialsOf(user.full_name || user.email) }
    localStorage.setItem('xmlforge_user', JSON.stringify(enriched))
    return enriched
  } catch {
    return null
  }
}

export async function apiLogout(): Promise<void> {
  try {
    await apiClient.post('/logout')
  } catch {
    // même si échec, on nettoie côté client
  } finally {
    localStorage.removeItem('xmlforge_token')
    localStorage.removeItem('xmlforge_user')
    sessionStorage.removeItem('xmlforge_unlocks')
  }
}

export function getStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem('xmlforge_user')
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('xmlforge_token')
}
