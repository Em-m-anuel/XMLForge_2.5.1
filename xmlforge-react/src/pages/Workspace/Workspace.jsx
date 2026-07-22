import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Button } from '../../components/Button/Button'
import { MonacoEditor } from '../../components/MonacoEditor/MonacoEditor'
import { useToast } from '../../components/Toast/Toast'
import { useDatabaseContext } from '../../context/DatabaseContext'
import { tableService } from '../../services/tableService'
import { columnService } from '../../services/columnService'
import { databaseService } from '../../services/databaseService'
import { converterService } from '../../services/converterService'
import apiClient from '../../services/api'
import { socketService } from '../../services/socketService'
import './Workspace.css'

function generateXmlForTable(table, columns){
  if(!table) return ''
  let xml = `<table name="${table.name}"`
  if(table.description) xml += ` description="${table.description.replace(/"/g,'&quot;')}"`
  if(table.comment) xml += ` comment="${table.comment.replace(/"/g,'&quot;')}"`
  if(table.is_protected) xml += ` protected="true"`
  if(table.file_identifier) xml += ` file_identifier="${table.file_identifier}"`
  if(table.status) xml += ` status="${table.status}"`
  xml += `>\n`
  columns.forEach(c=>{
    let attrs = `name="${c.name}" type="${c.type}"`
    if(c.length && c.length !== '-') attrs += ` length="${c.length}"`
    if(c.primary_key) attrs += ` primary_key="true"`
    if(c.foreign_key) attrs += ` foreign_key="true"`
    if(!c.nullable) attrs += ` nullable="false"`
    if(c.unique) attrs += ` unique="true"`
    if(c.auto_increment) attrs += ` auto_increment="true"`
    if(c.default) attrs += ` default="${c.default}"`
    if(c.comment) attrs += ` comment="${c.comment.replace(/"/g,'&quot;')}"`
    if(c.status && c.status !== 'ACTIVE') attrs += ` status="${c.status}"`
    xml += `  <column ${attrs} />\n`
  })
  xml += `</table>`
  return xml
}

function parseXmlTables(xmlString){
  try{
    const parser = new DOMParser()
    const doc = parser.parseFromString(xmlString, 'text/xml')
    const parserError = doc.getElementsByTagName('parsererror')
    if(parserError.length>0) return { valid:false, error:'XML invalide', tables:[] }
    let tableNodes = doc.getElementsByTagName('table')
    if(tableNodes.length===0){
      return { valid:false, error:'Aucune table trouvée', tables:[] }
    }
    const tables = []
    for(let i=0;i<tableNodes.length;i++){
      const tNode = tableNodes[i]
      const tName = tNode.getAttribute('name')
      if(!tName) continue
      const cols = []
      const colNodes = tNode.getElementsByTagName('column')
      for(let j=0;j<colNodes.length;j++){
        const cNode = colNodes[j]
        if(cNode.parentNode !== tNode) continue
        cols.push({
          name: cNode.getAttribute('name'),
          type: cNode.getAttribute('type') || 'VARCHAR',
          length: cNode.getAttribute('length') || '-',
          primary_key: cNode.getAttribute('primary_key')==='true' || cNode.getAttribute('primaryKey')==='true',
          foreign_key: cNode.getAttribute('foreign_key')==='true' || cNode.getAttribute('foreignKey')==='true',
          nullable: cNode.getAttribute('nullable')!=='false',
          unique: cNode.getAttribute('unique')==='true',
          auto_increment: cNode.getAttribute('autoIncrement')==='true' || cNode.getAttribute('auto_increment')==='true',
          default: cNode.getAttribute('default') || null,
          comment: cNode.getAttribute('comment') || ''
        })
      }
      tables.push({ name: tName, columns: cols, description: tNode.getAttribute('description')||'', comment: tNode.getAttribute('comment')||'', protected: tNode.getAttribute('protected')==='true', file_identifier: tNode.getAttribute('file_identifier')||'', status: tNode.getAttribute('status')||'ACTIVE' })
    }
    return { valid:true, tables }
  }catch(e){
    return { valid:false, error: e.message, tables:[] }
  }
}

export function Workspace(){
  const { dbName } = useParams()
  const [searchParams] = useSearchParams()
  const dbId = searchParams.get('dbId')
  const navigate = useNavigate()
  const { notify } = useToast()
  const { dbKey, saveKey } = useDatabaseContext()

  const [database, setDatabase] = useState(null)
  const [tables, setTables] = useState([])
  const [currentTable, setCurrentTable] = useState(null)
  const [columns, setColumns] = useState([])
  const [tab, setTab] = useState('structure')
  const [showNewTable, setShowNewTable] = useState(false)
  const [showEditCol, setShowEditCol] = useState(null)
  const [showDeleteTable, setShowDeleteTable] = useState(false)
  const [showUnlock, setShowUnlock] = useState(null)
  const [unlockKey, setUnlockKey] = useState('')
  const [newTableForm, setNewTableForm] = useState({ name:'', description:'', comment:'', is_protected:false, file_identifier:'' })
  const [showTableSettings, setShowTableSettings] = useState(false)
  const [tableSettingsForm, setTableSettingsForm] = useState({ name:'', description:'', comment:'', is_protected:false, file_identifier:'', status:'ACTIVE' })
  const [colForm, setColForm] = useState({ name:'', type:'VARCHAR', length:'255', nullable:true, primary_key:false, foreign_key:false, unique:false, auto_increment:false, default:'', comment:'' })
  const [xmlDraft, setXmlDraft] = useState('')
  const [sqlGenerated, setSqlGenerated] = useState('-- SQL généré apparaîtra ici\n-- Toujours généré depuis la base logique (XML -> Backend -> Base logique -> SQL)')
  const [converting, setConverting] = useState(false)
  const [editingComment, setEditingComment] = useState(null)
  const [commentDraft, setCommentDraft] = useState('')
  const [syncing, setSyncing] = useState(false)

  const fetchDatabase = useCallback(async ()=>{
    if(!dbId) return
    try{
      const data = await databaseService.get(dbId)
      setDatabase(data)
    }catch(err){
      notify('error','Erreur base', err.message)
    }
  },[dbId, notify])

  const fetchTables = useCallback(async ()=>{
    if(!dbId) return
    try{
      const data = await tableService.list(dbId)
      setTables(data)
      if(data.length && !currentTable){
        setCurrentTable(data[0])
      }
    }catch(err){
      notify('error','Erreur tables', err.message)
    }
  },[dbId, notify])

  const fetchColumns = useCallback(async (tableId)=>{
    if(!tableId) return
    try{
      const data = await columnService.list(tableId)
      setColumns(data)
    }catch(err){
      notify('error','Erreur colonnes', err.message)
    }
  },[notify])

  const openCommentEditor = (type, obj)=>{
    setEditingComment({ type, id: obj.id, name: obj.name })
    setCommentDraft(obj.comment || '')
  }

  const openTableSettings = ()=>{
    if(!currentTable) return
    setTableSettingsForm({
      name: currentTable.name,
      description: currentTable.description || '',
      comment: currentTable.comment || '',
      is_protected: currentTable.is_protected || false,
      file_identifier: currentTable.file_identifier || '',
      status: currentTable.status || 'ACTIVE'
    })
    setShowTableSettings(true)
  }

  const handleSaveTableSettings = async ()=>{
    if(!currentTable) return
    if(!requireKeyIfProtected(currentTable)) return
    try{
      const updated = await tableService.update(currentTable.id, {
        name: tableSettingsForm.name,
        description: tableSettingsForm.description,
        comment: tableSettingsForm.comment,
        is_protected: tableSettingsForm.is_protected,
        file_identifier: tableSettingsForm.file_identifier || null,
        status: tableSettingsForm.status
      }, dbKey)
      setTables(t=> t.map(x=> x.id===updated.id ? updated : x))
      setCurrentTable(updated)
      setShowTableSettings(false)
      notify('success','Paramètres table mis à jour','Protection, file_identifier, commentaire modifiables même après création')
    }catch(err){
      if(err.status===403) setShowUnlock(currentTable)
      notify('error','Erreur', err.message)
    }
  }

  useEffect(()=>{ fetchDatabase() },[fetchDatabase])
  useEffect(()=>{ fetchTables() },[fetchTables])
  useEffect(()=>{
    if(currentTable?.id){
      fetchColumns(currentTable.id)
    }
  },[currentTable, fetchColumns])

  useEffect(()=>{
    if(currentTable){
      const xml = generateXmlForTable(currentTable, columns)
      setXmlDraft(xml)
    }
  },[currentTable, columns])

  useEffect(()=>{
    socketService.connect()
    const unsubNewTable = socketService.on('new_table', (payload)=>{
      if(payload?.table?.database_id === Number(dbId)){
        notify('info','Nouvelle table',`${payload.by} a créé ${payload.table.name}`)
        fetchTables()
      }
    })
    const unsubMod = socketService.on('modification', ()=>{
      fetchTables()
      if(currentTable) fetchColumns(currentTable.id)
      fetchDatabase()
    })
    const unsubDel = socketService.on('suppression', ()=> fetchTables())
    return ()=>{ unsubNewTable(); unsubMod(); unsubDel() }
  },[dbId, currentTable, fetchTables, notify])

  const requireKeyIfProtected = useCallback((table)=>{
    if(!table?.is_protected) return true
    const key = dbKey || apiClient.getDbKey()
    if(!key){
      setShowUnlock(table)
      return false
    }
    return true
  },[dbKey])

  const handleCreateTable = async ()=>{
    if(!newTableForm.name.trim()){
      notify('error','Nom requis','Entrez un nom')
      return
    }
    try{
      const table = await tableService.create({
        name: newTableForm.name.trim(),
        description: newTableForm.description,
        database_id: Number(dbId),
        is_protected: newTableForm.is_protected,
        file_identifier: newTableForm.file_identifier || null,
        comment: newTableForm.comment
      })
      setTables(t=>[...t, table])
      setCurrentTable(table)
      setNewTableForm({ name:'', description:'', comment:'', is_protected:false, file_identifier:'' })
      setShowNewTable(false)
      notify('success','Table créée',`« ${table.name} » créée avec file_identifier ${table.file_identifier || '—'}`)
    }catch(err){
      notify('error','Erreur création', err.message)
    }
  }

  const handleDeleteTable = async ()=>{
    if(!currentTable) return
    if(!requireKeyIfProtected(currentTable)) return
    try{
      await tableService.delete(currentTable.id, dbKey)
      setTables(t=> t.filter(x=> x.id !== currentTable.id))
      setCurrentTable(null)
      setShowDeleteTable(false)
    }catch(err){
      if(err.status===403) setShowUnlock(currentTable)
      notify('error','Erreur', err.message)
    }
  }

  const handleConvertXmlToSql = async (xml = xmlDraft)=>{
    setConverting(true)
    try{
      const res = await converterService.xmlToSql(xml, database?.name)
      setSqlGenerated(res.sql)
    }catch(err){
      notify('error','Erreur conversion', err.message)
      setSqlGenerated(`-- Erreur: ${err.message}`)
    }finally{
      setConverting(false)
    }
  }

  const handleConvertSqlToXml = async ()=>{
    setConverting(true)
    try{
      const res = await converterService.sqlToXml(sqlGenerated, database?.name)
      setXmlDraft(res.xml)
    }catch(err){
      notify('error','Erreur conversion', err.message)
    }finally{
      setConverting(false)
    }
  }

  // V3 - XML source de vérité : sync via backend
  const handleSyncXmlToBackend = async ()=>{
    const parsed = parseXmlTables(xmlDraft)
    if(!parsed.valid){
      notify('error','XML invalide', parsed.error)
      return
    }
    if(parsed.tables.length===0){
      notify('error','Aucune table','Aucune table trouvée')
      return
    }
    setSyncing(true)
    try{
      const { syncService } = await import('../../services/syncService')
      const result = await syncService.syncDatabase(dbId, xmlDraft, dbKey)
      if(result.sql){
        setSqlGenerated(result.sql)
      }
      await fetchTables()
      if(currentTable?.id) await fetchColumns(currentTable.id)
      await fetchDatabase()
      notify('success','Synchronisation réussie',
        `${result.created_tables} table(s) créée(s), ${result.updated_tables} mise(s) à jour, ${result.created_columns} colonne(s) créée(s), ${result.updated_columns} modifiée(s), ${result.deleted_columns} supprimée(s). SQL régénéré depuis base logique.`
      )
    }catch(err){
      notify('error','Erreur synchronisation', err.message)
    }finally{
      setSyncing(false)
    }
  }

  const handleCopy = async (text)=>{
    try{
      await navigator.clipboard.writeText(text)
      notify('success','Copié','')
    }catch{
      notify('error','Erreur copie','')
    }
  }

  const handleDownload = (content, filename)=>{
    const blob = new Blob([content], {type:'text/plain'})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  if(!dbId){
    return (
      <div className="ws-empty">
        <p>Aucune base sélectionnée.</p>
        <button className="btn btn-primary" onClick={()=>navigate('/dashboard')}>Dashboard</button>
      </div>
    )
  }

  return (
    <div className="screen-workspace">
      <div className="ws-titlebar">
        <button className="back-btn" onClick={()=>navigate('/dashboard')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
          Bases
        </button>
        <div className="ws-crumb">/ <b>{database?.name || dbName}</b> / <span>{currentTable?.name || '—'}</span> {currentTable?.is_protected && <span>🔒</span>} {database?.key_identifier && <span style={{fontSize:10, opacity:.5, marginLeft:8}}>🔑 {database.key_identifier.slice(0,12)}...</span>}</div>
        <div className="ws-titlebar-right">
          <span className="badge badge-blue">{database?.status || 'ACTIVE'}</span>
          <button className="btn btn-sm" onClick={()=> database && openCommentEditor('database', database)}>💬 Base</button>
          <button className="btn btn-sm btn-primary" onClick={async ()=>{
            try{
              const mod = await import('../../services/exportService')
              await mod.exportService.exportXml(database.id, {download:true})
              notify('success','Export XML','Export contient toutes infos (description, commentaire, protection, file_identifier, archived...)')
            }catch(e){ notify('error','Erreur', e.message) }
          }}>XML</button>
          <button className="btn btn-sm btn-primary" onClick={async ()=>{
            try{
              const mod = await import('../../services/exportService')
              await mod.exportService.exportSql(database.id, {download:true})
              notify('success','Export SQL','SQL généré depuis base logique')
            }catch(e){ notify('error','Erreur', e.message) }
          }}>SQL</button>
        </div>
      </div>

      <div className="ws-body">
        <aside className="ws-sidebar">
          <div className="ws-sidebar-head">Tables ({tables.length})</div>
          <div className="ws-table-list">
            {tables.map(t=>(
              <button key={t.id} className={`ws-table-item ${currentTable?.id===t.id ? 'active' : ''}`} onClick={()=>setCurrentTable(t)}>
                <span className="ws-table-name">{t.is_protected ? '🔒 ' : ''}{t.name}</span>
                <span className="count">{t.columns_count ?? ''}</span>
                {t.is_protected && <span className="badge" style={{fontSize:8, background:'var(--danger-soft)', color:'#FF8787', marginLeft:4}}>Protégée</span>}
                {t.status==='ARCHIVED' && <span style={{fontSize:9}}>ARCH</span>}
              </button>
            ))}
          </div>
          <div className="ws-sidebar-actions">
            <button className="btn btn-sm" onClick={()=>setShowNewTable(true)}>＋ Nouvelle table</button>
          </div>
        </aside>

        <main className="ws-main">
          <div className="ws-main-head">
            <div className="ws-main-head-left">
              <h2>{currentTable?.name || 'Aucune table'} {currentTable?.is_protected && <span>🔒 <span className="badge" style={{background:'var(--danger-soft)', color:'#FF8787', fontSize:10}}>Protégée</span></span>}</h2>
              <div className="sub">
                {currentTable ? `${columns.length} colonnes · ${currentTable.status} · Modifié par ${currentTable.last_modified_by || currentTable.creator_name || '—'} ${currentTable.updated_at ? new Date(currentTable.updated_at).toLocaleString() : ''}` : 'Sélectionnez une table'}
                {currentTable?.uuid && <span style={{fontFamily:'var(--font-mono)', fontSize:10, marginLeft:8, opacity:.6}}>UUID {currentTable.uuid.slice(0,8)}...</span>}
                {currentTable?.file_identifier && <span style={{fontFamily:'var(--font-mono)', fontSize:10, marginLeft:8, opacity:.6}}>file_id {currentTable.file_identifier}</span>}
              </div>
              {currentTable?.comment && <div className="comment-box">💬 {currentTable.comment} <button className="btn btn-sm" onClick={()=>openCommentEditor('table', currentTable)}>Modifier</button></div>}
            </div>
            <div className="ws-main-actions">
              <button className="btn btn-sm" onClick={()=>{ setColForm({ name:'', type:'VARCHAR', length:'255', nullable:true, primary_key:false, foreign_key:false, unique:false, auto_increment:false, default:'', comment:'' }); setShowEditCol('new')}}>＋ Colonne</button>
              <button className="btn btn-sm" onClick={()=> currentTable && openCommentEditor('table', currentTable)}>💬 Commenter</button>
              <button className="btn btn-sm" onClick={()=>{ if(!currentTable) return; setTableSettingsForm({ name: currentTable.name, description: currentTable.description||'', comment: currentTable.comment||'', is_protected: currentTable.is_protected||false, file_identifier: currentTable.file_identifier||'', status: currentTable.status||'ACTIVE' }); setShowTableSettings(true)}}>⚙️ Paramètres (protection, file_id)</button>
              <button className="btn btn-sm btn-danger" onClick={()=>setShowDeleteTable(true)}>Supprimer</button>
            </div>
          </div>

          <div className="ws-tabs">
            <button className={tab==='structure' ? 'active' : ''} onClick={()=>setTab('structure')}>Structure</button>
            <button className={tab==='data' ? 'active' : ''} onClick={()=>setTab('data')}>Détails complets</button>
          </div>

          <div className="ws-tab-content">
            {tab==='structure' ? (
              <div className="table-wrap">
                <table className="cols-table">
                  <thead><tr><th>Nom</th><th>Type</th><th>Longueur</th><th>Nullable</th><th>PK</th><th>FK</th><th>Unique</th><th>AI</th><th>Commentaire</th><th>État</th><th>Actions</th></tr></thead>
                  <tbody>
                    {columns.map(c=>(
                      <tr key={c.id}>
                        <td className="col-name">{c.name}<div style={{fontSize:10, opacity:.6}}>par {c.last_modified_by || ''} · {c.uuid?.slice(0,6)}</div></td>
                        <td className="col-type">{c.type}</td>
                        <td>{c.length}</td>
                        <td>{c.nullable ? '✔' : '—'}</td>
                        <td>{c.primary_key ? <span className="pk-tag">PK</span> : '—'}</td>
                        <td>{c.foreign_key ? <span className="fk-tag">FK</span> : '—'}</td>
                        <td>{c.unique ? '✔' : '—'}</td>
                        <td>{c.auto_increment ? '✔' : '—'}</td>
                        <td>{c.comment || '—'}</td>
                        <td>{c.status}</td>
                        <td>
                          <div className="row-actions">
                            <button className="icon-btn" onClick={()=>openCommentEditor('column', c)}>💬</button>
                            <button className="icon-btn danger" onClick={async ()=>{
                              if(!confirm(`Supprimer ${c.name} ?`)) return
                              try{
                                const mod = await import('../../services/columnService')
                                await mod.columnService.delete(c.id, dbKey)
                                setColumns(col=>col.filter(x=>x.id!==c.id))
                              }catch(err){
                                if(err.status===403) setShowUnlock(currentTable)
                                notify('error','Erreur', err.message)
                              }
                            }}>🗑</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="table-wrap">
                <div className="grid-2">
                  <div className="card">
                    <h4>Base {database?.name}</h4>
                    <div className="kv"><b>UUID</b><span style={{fontFamily:'var(--font-mono)', fontSize:11}}>{database?.uuid}</span></div>
                    <div className="kv"><b>Nom</b><span>{database?.name}</span></div>
                    <div className="kv"><b>Description</b><span>{database?.description || '—'}</span></div>
                    <div className="kv"><b>Commentaire</b><span>{database?.comment || '—'}</span></div>
                    <div className="kv"><b>État</b><span>{database?.status}</span></div>
                    <div className="kv"><b>Clé</b><span style={{fontFamily:'var(--font-mono)', fontSize:10}}>{database?.key_identifier}</span></div>
                    <div className="kv"><b>Modifié par</b><span>{database?.last_modified_by || '—'}</span></div>
                  </div>
                  <div className="card">
                    <h4>Table {currentTable?.name}</h4>
                    {currentTable ? (
                      <>
                        <div className="kv"><b>UUID</b><span style={{fontFamily:'var(--font-mono)', fontSize:11}}>{currentTable.uuid}</span></div>
                        <div className="kv"><b>Nom</b><span>{currentTable.name}</span></div>
                        <div className="kv"><b>Description</b><span>{currentTable.description || '—'}</span></div>
                        <div className="kv"><b>Commentaire</b><span>{currentTable.comment || '—'}</span></div>
                        <div className="kv"><b>État</b><span>{currentTable.status}</span></div>
                        <div className="kv"><b>Protégée</b><span>{currentTable.is_protected ? `Oui 🔒 file_id ${currentTable.file_identifier || ''}` : 'Non'}</span></div>
                        <div className="kv"><b>Modifié par</b><span>{currentTable.last_modified_by || '—'}</span></div>
                      </>
                    ) : <span>Aucune table</span>}
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        <aside className="ws-right">
          <MonacoEditor title="XML Source" value={xmlDraft} onChange={setXmlDraft} language="xml" />
          <div className="ws-apply-row">
            <Button variant="primary" fullWidth onClick={()=>handleConvertXmlToSql()} disabled={converting}>
              {converting ? 'Conversion...' : '↓ Convertir XML → SQL (API)'}
            </Button>
            <Button fullWidth onClick={async ()=>{
              setSyncing(true)
              try{
                const { syncService } = await import('../../services/syncService')
                const result = await syncService.syncDatabase(dbId, xmlDraft, dbKey)
                setSqlGenerated(result.sql || sqlGenerated)
                await fetchTables()
                if(currentTable?.id) await fetchColumns(currentTable.id)
                await fetchDatabase()
                notify('success','Synchronisation réussie',`${result.created_tables} créée(s), ${result.updated_tables} maj, ${result.created_columns} col créée(s), ${result.deleted_columns} supprimée(s). SQL régénéré depuis base logique.`)
              }catch(e){
                notify('error','Erreur synchro', e.message)
              }finally{
                setSyncing(false)
              }
            }} disabled={syncing}>
              {syncing ? 'Synchronisation backend...' : 'Appliquer les modifications → Backend Sync + Refresh auto (XML source de vérité)'}
            </Button>
            <span className="ws-apply-hint">XML → POST /databases/{'{id}'}/sync-xml → Backend parse + création/maj/suppression tables/colonnes → sauvegarde → historique/audit → SocketIO → refresh Dashboard sans rechargement → SQL généré depuis base logique</span>
          </div>
          <MonacoEditor title="SQL généré (depuis base logique)" value={sqlGenerated} language="sql" readOnly onCopy={()=>handleCopy(sqlGenerated)} onDownload={()=>handleDownload(sqlGenerated, `${currentTable?.name || 'table'}.sql`)} />
          <div className="ws-apply-row">
            <Button fullWidth onClick={async ()=>{
              setConverting(true)
              try{
                const mod = await import('../../services/converterService')
                const res = await mod.converterService.sqlToXml(sqlGenerated, database?.name)
                setXmlDraft(res.xml)
              }catch(e){ notify('error','Erreur', e.message) }
              finally{ setConverting(false) }
            }} disabled={converting}>
              ↑ Convertir SQL → XML
            </Button>
          </div>
        </aside>
      </div>

      {showNewTable && (
        <div className="modal-overlay open" onClick={()=>setShowNewTable(false)}>
          <div className="modal" onClick={e=>e.stopPropagation()}>
            <div className="modal-head"><h3>Nouvelle table</h3><button className="icon-btn" onClick={()=>setShowNewTable(false)}>✕</button></div>
            <div className="modal-body">
              <div className="field-block"><label className="form-label">Nom *</label><input className="form-input" value={newTableForm.name} onChange={e=>setNewTableForm(f=>({...f, name:e.target.value}))} /></div>
              <div className="field-block"><label className="form-label">Description</label><input className="form-input" value={newTableForm.description} onChange={e=>setNewTableForm(f=>({...f, description:e.target.value}))} /></div>
              <div className="field-block"><label className="form-label">Commentaire</label><textarea className="form-input" rows={2} value={newTableForm.comment} onChange={e=>setNewTableForm(f=>({...f, comment:e.target.value}))} /></div>
              <label style={{display:'flex', gap:8, alignItems:'center'}}><input type="checkbox" checked={newTableForm.is_protected} onChange={e=>setNewTableForm(f=>({...f, is_protected:e.target.checked}))} /> ☐ Protéger cette table 🔒</label>
              {newTableForm.is_protected && (
                <div className="field-block" style={{marginTop:10}}>
                  <label className="form-label">Identifiant du fichier [file_identifier]</label>
                  <input className="form-input" value={newTableForm.file_identifier} onChange={e=>setNewTableForm(f=>({...f, file_identifier:e.target.value}))} placeholder="XML-9F4A-28BD-71A2 ou custom" />
                  <div style={{fontSize:11, color:'var(--text-tertiary)', marginTop:4}}>Si vide, utilisera clé base. Sinon ce file_identifier sera requis pour déverrouiller.</div>
                </div>
              )}
            </div>
            <div className="modal-footer"><button className="btn" onClick={()=>setShowNewTable(false)}>Annuler</button><button className="btn btn-primary" onClick={async ()=>{
              try{
                const t = await tableService.create({ name: newTableForm.name.trim(), description: newTableForm.description, database_id: Number(dbId), is_protected: newTableForm.is_protected, file_identifier: newTableForm.file_identifier || null, comment: newTableForm.comment })
                setTables(prev=>[...prev, t]); setCurrentTable(t); setShowNewTable(false)
              }catch(err){ notify('error','Erreur', err.message) }
            }}>Créer</button></div>
          </div>
        </div>
      )}

      {showTableSettings && (
        <div className="modal-overlay open" onClick={()=>setShowTableSettings(false)}>
          <div className="modal" onClick={e=>e.stopPropagation()}>
            <div className="modal-head"><h3>⚙️ Paramètres table : {currentTable?.name}</h3><button className="icon-btn" onClick={()=>setShowTableSettings(false)}>✕</button></div>
            <div className="modal-body">
              <div className="field-block"><label className="form-label">Nom</label><input className="form-input" value={tableSettingsForm.name} onChange={e=>setTableSettingsForm(f=>({...f, name:e.target.value}))} /></div>
              <div className="field-block"><label className="form-label">Description</label><input className="form-input" value={tableSettingsForm.description} onChange={e=>setTableSettingsForm(f=>({...f, description:e.target.value}))} /></div>
              <div className="field-block"><label className="form-label">Commentaire</label><textarea className="form-input" rows={2} value={tableSettingsForm.comment} onChange={e=>setTableSettingsForm(f=>({...f, comment:e.target.value}))} /></div>
              <div className="field-block"><label className="form-label">État</label><select className="form-input" value={tableSettingsForm.status} onChange={e=>setTableSettingsForm(f=>({...f, status:e.target.value}))}><option value="ACTIVE">ACTIVE</option><option value="ARCHIVED">ARCHIVED</option></select></div>
              <label style={{display:'flex', gap:8, alignItems:'center', marginTop:8}}><input type="checkbox" checked={tableSettingsForm.is_protected} onChange={e=>setTableSettingsForm(f=>({...f, is_protected:e.target.checked}))} /> Protéger cette table</label>
              {tableSettingsForm.is_protected && (
                <div className="field-block" style={{marginTop:10}}>
                  <label className="form-label">Identifiant du fichier [file_identifier] – modifiable après création</label>
                  <input className="form-input" value={tableSettingsForm.file_identifier} onChange={e=>setTableSettingsForm(f=>({...f, file_identifier:e.target.value}))} placeholder="XML-9F4A-28BD-71A2" />
                  <div style={{fontSize:11, color:'var(--text-tertiary)', marginTop:4}}>Permet protéger/retirer protection, modifier file_identifier même après création (spec 5).</div>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={()=>setShowTableSettings(false)}>Annuler</button>
              <button className="btn btn-primary" onClick={async ()=>{
                try{
                  const updated = await tableService.update(currentTable.id, {
                    name: tableSettingsForm.name,
                    description: tableSettingsForm.description,
                    comment: tableSettingsForm.comment,
                    is_protected: tableSettingsForm.is_protected,
                    file_identifier: tableSettingsForm.file_identifier || null,
                    status: tableSettingsForm.status
                  }, dbKey)
                  setTables(t=> t.map(x=> x.id===updated.id ? updated : x))
                  setCurrentTable(updated)
                  setShowTableSettings(false)
                  notify('success','Paramètres mis à jour','Protection, file_identifier modifiables après création')
                }catch(err){
                  if(err.status===403) setShowUnlock(currentTable)
                  notify('error','Erreur', err.message)
                }
              }}>Enregistrer</button>
            </div>
          </div>
        </div>
      )}

      {showUnlock && (
        <div className="modal-overlay open">
          <div className="modal">
            <div className="modal-head"><h3>🔒 Table protégée : {showUnlock.name} <span className="badge" style={{background:'var(--danger-soft)', color:'#FF8787'}}>Protégée</span></h3></div>
            <div className="modal-body">
              <p className="desc">Lecture toujours autorisée. Modification, suppression, ajout/modif/suppression colonne impossible sans identifiant.</p>
              <div className="field-block"><label className="form-label">Clé Identifiant (file_identifier ou clé base)</label><input className="form-input" value={unlockKey} onChange={e=>setUnlockKey(e.target.value)} placeholder="XML-XXXX-XXXX-XXXX" /></div>
              {showUnlock.file_identifier && <div style={{fontSize:11}}>File ID attendu : <code>{showUnlock.file_identifier}</code></div>}
              {database?.key_identifier && <div style={{fontSize:11, color:'var(--text-tertiary)'}}>Clé base : {database.key_identifier}</div>}
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={()=>{ setShowUnlock(null); setUnlockKey('') }}>Annuler</button>
              <button className="btn btn-primary" onClick={async ()=>{
                try{
                  await tableService.unlock(showUnlock.id, unlockKey)
                  apiClient.setDbKey(unlockKey)
                  saveKey(unlockKey)
                  setShowUnlock(null)
                  setUnlockKey('')
                  notify('success','Déverrouillée','')
                }catch(err){ notify('error','Clé invalide', err.message) }
              }}>Déverrouiller et poursuivre</button>
            </div>
          </div>
        </div>
      )}

      {editingComment && (
        <div className="modal-overlay open">
          <div className="modal">
            <div className="modal-head"><h3>💬 Commentaire {editingComment.type} : {editingComment.name}</h3><button className="icon-btn" onClick={()=>setEditingComment(null)}>✕</button></div>
            <div className="modal-body">
              <textarea className="form-input" rows={4} value={commentDraft} onChange={e=>setCommentDraft(e.target.value)} placeholder="Commentaire libre..." />
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={()=>setEditingComment(null)}>Annuler</button>
              <button className="btn btn-primary" onClick={async ()=>{
                try{
                  if(editingComment.type==='database'){
                    await databaseService.updateComment(editingComment.id, commentDraft)
                  }else if(editingComment.type==='table'){
                    await tableService.updateComment(editingComment.id, commentDraft, dbKey)
                  }else{
                    const { columnService } = await import('../../services/columnService')
                    await columnService.updateComment(editingComment.id, commentDraft, dbKey)
                  }
                  setEditingComment(null)
                  notify('success','Commentaire mis à jour','')
                  fetchTables()
                  if(currentTable) fetchColumns(currentTable.id)
                  fetchDatabase()
                }catch(err){ notify('error','Erreur', err.message) }
              }}>Enregistrer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
