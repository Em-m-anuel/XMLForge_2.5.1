import { useEffect, useState } from 'react'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { Navbar } from '../../components/Navbar/Navbar'
import { auditService } from '../../services/auditService'
import { useToast } from '../../components/Toast/Toast'
import { SkeletonTable } from '../../components/Skeleton/Skeleton'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { Button } from '../../components/Button/Button'
import { Badge } from '../../components/Badge/Badge'
import { Icons } from '../../utils/icons'
import './Audit.css'

const actionColors = {
  CONNEXION: 'green',
  DECONNEXION: 'blue',
  INSCRIPTION: 'green',
  CREATION_BASE: 'blue',
  MODIFICATION_BASE: 'blue',
  SUPPRESSION_BASE: 'red',
  ARCHIVAGE_BASE: 'blue',
  RESTAURATION_BASE: 'green',
  COMMENTAIRE_BASE: 'blue',
  CREATION_TABLE: 'blue',
  MODIFICATION_TABLE: 'blue',
  SUPPRESSION_TABLE: 'red',
  ARCHIVAGE_TABLE: 'blue',
  RESTAURATION_TABLE: 'green',
  COMMENTAIRE_TABLE: 'blue',
  CREATION_COLONNE: 'blue',
  MODIFICATION_COLONNE: 'blue',
  SUPPRESSION_COLONNE: 'red',
  IMPORT_XML: 'green',
  IMPORT_SQL: 'green',
  EXPORT_XML: 'blue',
  EXPORT_SQL: 'blue',
  CONVERSION_XML: 'blue',
  CONVERSION_SQL: 'blue',
  DEVERROUILLAGE_TABLE: 'green',
  CREATION_REELLE_BASE: 'green',
  ERREUR_CONNEXION: 'red',
  ERREUR: 'red',
}

export function AuditPage(){
  const { notify } = useToast()
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  const fetchLogs = async ()=>{
    setLoading(true)
    try{
      const data = await auditService.list(200)
      setLogs(data)
    }catch(err){
      notify('error','Erreur audit', err.message)
    }finally{
      setLoading(false)
    }
  }

  useEffect(()=>{ fetchLogs() },[])

  const filtered = logs.filter(l=>{
    if(filter!=='all' && !l.action?.includes(filter.toUpperCase())) return false
    if(search){
      const q = search.toLowerCase()
      return (l.user_name?.toLowerCase().includes(q) || l.action?.toLowerCase().includes(q) || l.element_name?.toLowerCase().includes(q) || l.description?.toLowerCase().includes(q))
    }
    return true
  })

  return (
    <div className="screen-dashboard">
      <Sidebar onSettings={()=>notify('info','Paramètres','Bientôt disponible.')} />
      <div className="dash-main">
        <Navbar searchValue={search} onSearchChange={setSearch} />

        <div className="dash-content">
          <div className="dash-head">
            <div>
              <h1>Audit Log</h1>
              <p>{filtered.length} événements d'audit · Connexions, créations, imports, exports, conversions, erreurs · Visible uniquement par nyx@xmlforge.io (préparé pour rôles ADMIN)</p>
            </div>
            <div className="dash-actions">
              <select className="form-input" value={filter} onChange={e=>setFilter(e.target.value)} style={{width:200, height:36}}>
                <option value="all">Toutes les actions</option>
                <option value="CONNEXION">Connexions</option>
                <option value="CREATION">Créations</option>
                <option value="SUPPRESSION">Suppressions</option>
                <option value="IMPORT">Imports</option>
                <option value="EXPORT">Exports</option>
                <option value="CONVERSION">Conversions</option>
                <option value="ARCHIVAGE">Archivages</option>
                <option value="COMMENTAIRE">Commentaires</option>
                <option value="ERREUR">Erreurs</option>
              </select>
              <Button size="sm" onClick={fetchLogs}>Actualiser</Button>
            </div>
          </div>

          {loading ? <SkeletonTable rows={10} /> :
           filtered.length===0 ? <EmptyState icon={Icons.shield} title="Aucun log d'audit" description="Aucune action enregistrée ou filtre trop restrictif." /> :
           (
            <div className="audit-table-wrap">
              <table className="cols-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Utilisateur</th>
                    <th>Action</th>
                    <th>Élément</th>
                    <th>Description</th>
                    <th>IP</th>
                    <th>Meta</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(log=>(
                    <tr key={log.id}>
                      <td style={{fontFamily:'var(--font-mono)', fontSize:11}}>{new Date(log.timestamp).toLocaleString('fr-FR')}</td>
                      <td><div style={{fontWeight:600}}>{log.user_name || '—'}</div><div style={{fontSize:10, color:'var(--text-tertiary)'}}>ID {log.user_id || '—'} · {log.uuid?.slice(0,8)}</div></td>
                      <td><Badge variant={actionColors[log.action] || 'blue'}>{log.action}</Badge></td>
                      <td>
                        <div style={{fontWeight:600}}>{log.element_name || '—'}</div>
                        <div style={{fontSize:11, color:'var(--text-tertiary)'}}>{log.element_type || ''}</div>
                      </td>
                      <td style={{maxWidth:320}}><div style={{fontSize:13}}>{log.description}</div></td>
                      <td style={{fontFamily:'var(--font-mono)', fontSize:11}}>{log.ip_address || '—'}</td>
                      <td><details><summary style={{cursor:'pointer', fontSize:11, color:'var(--text-secondary)'}}>Meta</summary><pre style={{fontSize:10, maxWidth:200, overflow:'auto'}}>{log.meta_data?.slice(0,300) || '—'}</pre></details></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
           )
          }
        </div>
      </div>
    </div>
  )
}
