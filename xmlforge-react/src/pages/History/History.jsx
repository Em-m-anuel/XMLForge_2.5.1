import { useEffect, useState } from 'react'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { Navbar } from '../../components/Navbar/Navbar'
import { historyService } from '../../services/historyService'
import { useToast } from '../../components/Toast/Toast'
import { SkeletonTable } from '../../components/Skeleton/Skeleton'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { Button } from '../../components/Button/Button'
import { Badge } from '../../components/Badge/Badge'
import { Icons } from '../../utils/icons'
import './History.css'

function formatDate(iso){
  if(!iso) return '—'
  const d = new Date(iso)
  const today = new Date()
  const isToday = d.toDateString() === today.toDateString()
  const yesterday = new Date(today); yesterday.setDate(today.getDate()-1)
  const isYesterday = d.toDateString() === yesterday.toDateString()
  let dayLabel = d.toLocaleDateString('fr-FR', { day:'numeric', month:'long' })
  if(isToday) dayLabel = "Aujourd'hui"
  else if(isYesterday) dayLabel = "Hier"
  return `${dayLabel} à ${d.toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'})}`
}

function groupByDate(items){
  const groups = {}
  items.forEach(item=>{
    const date = new Date(item.created_at || item.date)
    const key = date.toDateString()
    if(!groups[key]){
      const today = new Date().toDateString()
      const yesterday = new Date(); yesterday.setDate(yesterday.getDate()-1)
      let label = date.toLocaleDateString('fr-FR', { weekday:'long', day:'numeric', month:'long', year:'numeric' })
      if(key === today) label = "Aujourd'hui"
      else if(key === yesterday.toDateString()) label = "Hier"
      groups[key] = { label, items: [] }
    }
    groups[key].items.push(item)
  })
  return Object.values(groups)
}

export function HistoryPage(){
  const { notify } = useToast()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [databaseFilter, setDatabaseFilter] = useState('')
  const [search, setSearch] = useState('')

  const fetchHistory = async ()=>{
    setLoading(true)
    try{
      const data = await historyService.list(200, databaseFilter ? Number(databaseFilter) : null)
      setHistory(data)
    }catch(err){
      notify('error','Erreur historique', err.message)
    }finally{
      setLoading(false)
    }
  }

  useEffect(()=>{ fetchHistory() },[databaseFilter])

  const filtered = history.filter(h=>{
    if(filter!=='all' && h.element_type !== filter) return false
    if(search){
      const q = search.toLowerCase()
      return (h.user_name?.toLowerCase().includes(q) || h.element_name?.toLowerCase().includes(q) || h.description?.toLowerCase().includes(q))
    }
    return true
  })

  const grouped = groupByDate(filtered)

  return (
    <div className="screen-dashboard">
      <Sidebar onSettings={()=>notify('info','Paramètres','Bientôt disponible.')} />
      <div className="dash-main">
        <Navbar searchValue={search} onSearchChange={setSearch} />

        <div className="dash-content">
          <div className="dash-head">
            <div>
              <h1>Historique des actions</h1>
              <p>{filtered.length} événements · Timeline détaillée avec UUID, IP, avant/après · Visible uniquement par nyx@xmlforge.io (préparé pour rôles ADMIN)</p>
            </div>
            <div className="dash-actions">
              <select className="form-input" value={filter} onChange={e=>setFilter(e.target.value)} style={{width:160, height:36}}>
                <option value="all">Tous les éléments</option>
                <option value="base">Bases</option>
                <option value="table">Tables</option>
                <option value="colonne">Colonnes</option>
              </select>
              <input className="form-input" placeholder="Database ID" value={databaseFilter} onChange={e=>setDatabaseFilter(e.target.value)} style={{width:130, height:36}} />
              <Button size="sm" onClick={fetchHistory}>Actualiser</Button>
            </div>
          </div>

          {loading ? (
            <SkeletonTable rows={8} />
          ) : filtered.length===0 ? (
            <EmptyState icon={Icons.db} title="Aucun historique" description="Aucune action enregistrée pour le moment ou filtre trop restrictif." />
          ) : (
            <div className="timeline">
              {grouped.map((group, gi)=>(
                <div key={gi} className="timeline-group">
                  <div className="timeline-date">{group.label}</div>
                  <div className="timeline-items">
                    {group.items.map(item=>(
                      <div key={item.id} className="timeline-item">
                        <div className="timeline-dot" />
                        <div className="timeline-card">
                          <div className="timeline-card-header">
                            <span className="timeline-user">{item.user_name}</span>
                            <span className="timeline-action">{item.action_type}</span>
                            <span className="timeline-element">{item.element_name}</span>
                            <span className="timeline-time">{formatDate(item.created_at)}</span>
                          </div>
                          <div className="timeline-card-body">
                            <div className="timeline-type">{item.element_type}</div>
                            <div className="timeline-desc">{item.description}</div>
                            {item.ip_address && <div className="timeline-ip">IP: {item.ip_address} · UUID: {item.uuid?.slice(0,8)}...</div>}
                            <div style={{display:'flex', gap:8, marginTop:8, flexWrap:'wrap'}}>
                              {item.before && <details className="timeline-details"><summary>Avant</summary><pre>{typeof item.before === 'string' ? item.before.slice(0,500) : JSON.stringify(item.before).slice(0,500)}</pre></details>}
                              {item.after && <details className="timeline-details"><summary>Après</summary><pre>{typeof item.after === 'string' ? item.after.slice(0,500) : JSON.stringify(item.after).slice(0,500)}</pre></details>}
                            </div>
                          </div>
                          <div className="timeline-card-footer">
                            <Badge variant="blue">{item.element_type}</Badge>
                            {item.database_id && <Badge variant="blue">DB {item.database_id}</Badge>}
                            {item.table_id && <Badge variant="green">Table {item.table_id}</Badge>}
                            <span className="dim" style={{fontSize:10, fontFamily:'var(--font-mono)'}}>{item.uuid?.slice(0,8)}...</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
