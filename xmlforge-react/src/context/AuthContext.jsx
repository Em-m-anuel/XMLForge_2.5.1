import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import { authService } from '../services/authService'
import apiClient from '../services/api'
import { socketService } from '../services/socketService'

function extractRoles(user) {
  if (!user) return []
  if (Array.isArray(user.roles) && user.roles.length) return user.roles.map(role => String(role).toUpperCase())
  if (user.role) return [String(user.role).toUpperCase()]
  if (user.is_admin === true) return ['ADMIN']
  return ['USER']
}

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authService.getStoredUser())
  const [loading, setLoading] = useState(true)

  const roles = useMemo(() => extractRoles(user), [user])
  const isAdmin = roles.includes('ADMIN')

  const clearLocalAuth = useCallback(() => {
    setUser(null)
    socketService.disconnect()
    window.dispatchEvent(new CustomEvent('xmlforge:session-changed', { detail: { authenticated: false } }))
  }, [])

  const checkAuth = useCallback(async () => {
    const token = apiClient.getToken()
    if (!token || apiClient.isTokenExpired(token)) {
      if (token) apiClient.clearSession('expired')
      clearLocalAuth()
      setLoading(false)
      return
    }
    try {
      const currentUser = await authService.me()
      setUser(currentUser)
      localStorage.setItem('xmlforge_user', JSON.stringify(currentUser))
      socketService.connect()
    } catch {
      clearLocalAuth()
    } finally {
      setLoading(false)
    }
  }, [clearLocalAuth])

  useEffect(() => { checkAuth() }, [checkAuth])

  useEffect(() => {
    const unauthorized = () => clearLocalAuth()
    window.addEventListener('xmlforge:unauthorized', unauthorized)
    return () => window.removeEventListener('xmlforge:unauthorized', unauthorized)
  }, [clearLocalAuth])

  const login = async (payload) => {
    const data = await authService.login(payload)
    setUser(data.user)
    window.dispatchEvent(new CustomEvent('xmlforge:session-changed', { detail: { authenticated: true } }))
    socketService.connect()
    return data
  }

  const register = (payload) => authService.register(payload)

  const logout = async () => {
    await authService.logout()
    clearLocalAuth()
  }

  const hasRole = useCallback((role) => roles.includes(String(role).toUpperCase()), [roles])
  const hasAnyRole = useCallback((wanted = []) => wanted.some(role => roles.includes(String(role).toUpperCase())), [roles])

  return (
    <AuthContext.Provider value={{
      user, roles, isAdmin, isPrivileged: isAdmin, hasRole, hasAnyRole,
      loading, login, register, logout, refreshUser: checkAuth,
      isAuthenticated: Boolean(user),
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be inside AuthProvider')
  return context
}
