import { useState, useCallback, useEffect } from 'react'
import { databaseService } from '../services/databaseService'
import { useToast } from '../components/Toast/Toast'

export function useDatabases(){
  const [databases, setDatabases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { notify } = useToast()

  const fetchDatabases = useCallback(async (includeArchived=true)=>{
    setLoading(true)
    setError(null)
    try{
      const data = await databaseService.list(includeArchived)
      setDatabases(data)
      return data
    }catch(err){
      setError(err.message)
      notify('error','Erreur','Impossible de charger les bases: '+err.message)
      return []
    }finally{
      setLoading(false)
    }
  },[notify])

  useEffect(()=>{ fetchDatabases() },[fetchDatabases])

  const createDatabase = useCallback(async (payload)=>{
    try{
      const data = await databaseService.create(payload)
      setDatabases(d=> [data, ...d])
      notify('success','Base créée',`« ${data.name} » créée.`)
      return data
    }catch(err){
      notify('error','Erreur création',err.message)
      throw err
    }
  },[notify])

  const updateDatabase = useCallback(async (id, payload)=>{
    const data = await databaseService.update(id, payload)
    setDatabases(d=> d.map(b=> b.id===id ? {...b, ...data} : b))
    return data
  },[])

  const deleteDatabase = useCallback(async (id)=>{
    await databaseService.delete(id)
    setDatabases(d=> d.filter(b=> b.id!==id))
  },[])

  const archiveDatabase = useCallback(async (id)=>{
    const data = await databaseService.archive(id)
    setDatabases(d=> d.map(b=> b.id===id ? {...b, ...data} : b))
    return data
  },[])

  const restoreDatabase = useCallback(async (id)=>{
    const data = await databaseService.restore(id)
    setDatabases(d=> d.map(b=> b.id===id ? {...b, ...data} : b))
    return data
  },[])

  const filteredDbs = useCallback((query)=>{
    if(!query) return databases
    const q=query.toLowerCase()
    return databases.filter(d=> d.name.toLowerCase().includes(q))
  },[databases])

  return {
    databases,
    loading,
    error,
    fetchDatabases,
    createDatabase,
    updateDatabase,
    deleteDatabase,
    archiveDatabase,
    restoreDatabase,
    filteredDbs
  }
}
