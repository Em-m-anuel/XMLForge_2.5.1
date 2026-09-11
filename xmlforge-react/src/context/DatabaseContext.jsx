import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { useAuth } from './AuthContext'
import { unlockService } from '../services/unlockService'

const DatabaseContext = createContext(null)

function readUnlockIds() {
  try {
    return JSON.parse(sessionStorage.getItem('xmlforge_unlocks') || '[]').map(String)
  } catch {
    return []
  }
}

export function DatabaseProvider({ children }) {
  const { isAuthenticated } = useAuth()
  const [currentDatabase, setCurrentDatabase] = useState(null)
  const [unlockedTableIds, setUnlockedTableIds] = useState(readUnlockIds)

  const persist = useCallback((ids) => {
    const unique = [...new Set(ids.map(String))]
    sessionStorage.setItem('xmlforge_unlocks', JSON.stringify(unique))
    setUnlockedTableIds(unique)
  }, [])

  const refreshUnlocks = useCallback(async () => {
    if (!isAuthenticated) {
      persist([])
      return []
    }
    try {
      const unlocks = await unlockService.list()
      const ids = (unlocks || []).filter(item => !item.is_expired).map(item => item.table_id)
      persist(ids)
      return ids
    } catch {
      persist([])
      return []
    }
  }, [isAuthenticated, persist])

  useEffect(() => { refreshUnlocks() }, [refreshUnlocks])

  useEffect(() => {
    const sessionChanged = () => refreshUnlocks()
    window.addEventListener('xmlforge:session-changed', sessionChanged)
    return () => window.removeEventListener('xmlforge:session-changed', sessionChanged)
  }, [refreshUnlocks])

  const markUnlocked = useCallback((tableId) => {
    persist([...unlockedTableIds, String(tableId)])
  }, [persist, unlockedTableIds])

  const clearUnlocks = useCallback(async ({ backend = false } = {}) => {
    if (backend && isAuthenticated) {
      try { await unlockService.clear() } catch { /* session cleanup stays local */ }
    }
    persist([])
  }, [isAuthenticated, persist])

  const isUnlocked = useCallback((tableId) => unlockedTableIds.includes(String(tableId)), [unlockedTableIds])

  return (
    <DatabaseContext.Provider value={{
      currentDatabase, setCurrentDatabase,
      unlockedTableIds, markUnlocked, refreshUnlocks, clearUnlocks, isUnlocked,
    }}>
      {children}
    </DatabaseContext.Provider>
  )
}

export function useDatabaseContext() {
  const context = useContext(DatabaseContext)
  if (!context) throw new Error('useDatabaseContext must be inside DatabaseProvider')
  return context
}
