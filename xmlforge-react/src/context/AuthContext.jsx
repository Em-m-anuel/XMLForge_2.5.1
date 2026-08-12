import { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import { authService } from '../services/authService'
import { socketService } from '../services/socketService'

const ADMIN_EMAIL = 'nyx@xmlforge.io'

function extractRoles(user){
  if(!user) return []
  if(Array.isArray(user.roles) && user.roles.length){
    return user.roles
  }
  if(user.email?.toLowerCase() === ADMIN_EMAIL){
    return ['ADMIN']
  }
  if(user.is_admin){
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
  const isAdmin = useMemo(()=> {
    if(!user) return false
    return user.email?.toLowerCase() === ADMIN_EMAIL || user.is_admin === true || roles.includes('ADMIN')
  }, [user, roles])
  const isPrivileged = useMemo(()=> isAdmin, [isAdmin])

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
      sessionStorage.removeItem('xmlforge_unlocks')
      // Clear personal unlocks backend via API? logout will do, but here just clear local
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
    try{
      await authService.logout()
    }catch{}
    // V4: clear personal unlocks
    try{
      sessionStorage.removeItem('xmlforge_unlocks')
      sessionStorage.removeItem('xmlforge_db_key')
      localStorage.removeItem('xmlforge_unlocks')
    }catch{}
    setUser(null)
    socketService.disconnect()
  }

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
