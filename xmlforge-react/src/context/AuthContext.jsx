import { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import { authService } from '../services/authService'
import { socketService } from '../services/socketService'

// Liste temporaire des emails admin - facile à remplacer par un vrai système de rôles plus tard
const ADMIN_EMAILS = ['nyx@xmlforge.io']

function extractRoles(user){
  // Préparation future : si user.roles existe (array), on l'utilise, sinon on déduit du email
  if(!user) return []
  if(Array.isArray(user.roles) && user.roles.length){
    return user.roles
  }
  // Fallback temporaire : email admin
  if(ADMIN_EMAILS.includes(user.email?.toLowerCase())){
    return ['ADMIN']
  }
  return ['USER']
}

const AuthContext = createContext(null)

export function AuthProvider({ children }){
  const [user, setUser] = useState(()=>{
    try { return JSON.parse(localStorage.getItem('xmlforge_user') || 'null') } catch { return null }
  })
  const [loading, setLoading] = useState(true)

  const roles = useMemo(()=> extractRoles(user), [user])
  const isAdmin = useMemo(()=> roles.includes('ADMIN'), [roles])
  const isPrivileged = useMemo(()=> isAdmin, [isAdmin]) // alias pour historique/audit

  const checkAuth = useCallback(async ()=>{
    const token = localStorage.getItem('xmlforge_token')
    if(!token){
      setLoading(false)
      return
    }
    try{
      const res = await authService.me()
      setUser(res)
      localStorage.setItem('xmlforge_user', JSON.stringify(res))
      socketService.connect()
    }catch{
      localStorage.removeItem('xmlforge_token')
      localStorage.removeItem('xmlforge_user')
      sessionStorage.removeItem('xmlforge_db_key')
      setUser(null)
      socketService.disconnect()
    }finally{
      setLoading(false)
    }
  },[])

  useEffect(()=>{ checkAuth() },[checkAuth])

  const login = async (payload)=>{
    const data = await authService.login(payload)
    setUser(data.user)
    socketService.connect()
    return data
  }

  const register = async (payload)=>{
    const data = await authService.register(payload)
    return data
  }

  const logout = async ()=>{
    await authService.logout()
    setUser(null)
    socketService.disconnect()
  }

  // Helper pour vérifier permission future
  const hasRole = useCallback((role)=>{
    return roles.includes(role)
  },[roles])

  const hasAnyRole = useCallback((wantedRoles=[])=>{
    return wantedRoles.some(r=> roles.includes(r))
  },[roles])

  return (
    <AuthContext.Provider value={{
      user,
      roles,
      isAdmin,
      isPrivileged,
      hasRole,
      hasAnyRole,
      loading,
      login,
      register,
      logout,
      isAuthenticated: !!user
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(){
  const ctx = useContext(AuthContext)
  if(!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
