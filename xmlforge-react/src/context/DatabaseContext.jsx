import { createContext, useContext, useState, useCallback } from 'react'

const DatabaseContext = createContext(null)

export function DatabaseProvider({ children }){
  const [currentDatabase, setCurrentDatabase] = useState(null)
  const [dbKey, setDbKey] = useState(()=> sessionStorage.getItem('xmlforge_db_key') || null)

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

  return (
    <DatabaseContext.Provider value={{ currentDatabase, setCurrentDatabase, dbKey, saveKey, clearKey }}>
      {children}
    </DatabaseContext.Provider>
  )
}

export function useDatabaseContext(){
  const ctx = useContext(DatabaseContext)
  if(!ctx) throw new Error('useDatabaseContext must be inside DatabaseProvider')
  return ctx
}
