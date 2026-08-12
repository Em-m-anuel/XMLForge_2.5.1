import { createContext, useContext, useState, useCallback } from 'react'

const DatabaseContext = createContext(null)

function loadUnlocks() {
  try {
    const raw = sessionStorage.getItem('xmlforge_unlocks')
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export function DatabaseProvider({ children }){
  const [currentDatabase, setCurrentDatabase] = useState(null)
  const [dbKey, setDbKey] = useState(()=> sessionStorage.getItem('xmlforge_db_key') || null)
  const [unlocks, setUnlocks] = useState(()=> loadUnlocks()) // {tableId: key}

  const saveKey = useCallback((key)=>{
    if(key){
      sessionStorage.setItem('xmlforge_db_key', key)
      setDbKey(key)
    }
  },[])

  const clearKey = useCallback(()=>{
    sessionStorage.removeItem('xmlforge_db_key')
    setDbKey(null)
  },[])

  const saveUnlock = useCallback((tableId, key)=>{
    setUnlocks(prev => {
      const next = { ...prev, [String(tableId)]: key }
      sessionStorage.setItem('xmlforge_unlocks', JSON.stringify(next))
      return next
    })
    // Also keep legacy dbKey for backward compat
    if(key) saveKey(key)
  },[saveKey])

  const getUnlock = useCallback((tableId)=>{
    return unlocks[String(tableId)] || null
  },[unlocks])

  const clearUnlocks = useCallback(()=>{
    sessionStorage.removeItem('xmlforge_unlocks')
    sessionStorage.removeItem('xmlforge_db_key')
    setUnlocks({})
    setDbKey(null)
  },[])

  const isUnlocked = useCallback((tableId)=>{
    return !!unlocks[String(tableId)]
  },[unlocks])

  return (
    <DatabaseContext.Provider value={{ 
      currentDatabase, setCurrentDatabase, 
      dbKey, saveKey, clearKey,
      unlocks, saveUnlock, getUnlock, clearUnlocks, isUnlocked
    }}>
      {children}
    </DatabaseContext.Provider>
  )
}

export function useDatabaseContext(){
  const ctx = useContext(DatabaseContext)
  if(!ctx) throw new Error('useDatabaseContext must be inside DatabaseProvider')
  return ctx
}
