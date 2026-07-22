import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { Navbar } from '../../components/Navbar/Navbar'
import { Button } from '../../components/Button/Button'
import { IconButton } from '../../components/IconButton/IconButton'
import { ContextMenu } from '../../components/ContextMenu/ContextMenu'
import { Modal } from '../../components/Modal/Modal'
import { FormInput } from '../../components/Input/Input'
import { Badge } from '../../components/Badge/Badge'
import { SkeletonCard } from '../../components/Skeleton/Skeleton'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { useToast } from '../../components/Toast/Toast'
import { useDatabases } from '../../hooks/useDatabases'
import { databaseService } from '../../services/databaseService'
import { importService } from '../../services/importService'
import { exportService } from '../../services/exportService'
import { Icons } from '../../utils/icons'
import './Dashboard.css'
import { useEffect } from 'react'

function DatabaseCard({ db, index, onOpen, onEdit, onDelete, onArchive, onRestore, onExportXml, onExportSql }){
  const isArchived = db.status === 'ARCHIVED'
  return (
    <div className={`db-card ${isArchived ? 'archived' : ''}`} style={{animationDelay:`${index*0.05}s`}}>
      <div className="db-card-top">
        <div className="db-card-icon">{Icons.db}</div>
        <div style={{display:'flex', gap:6, alignItems:'center'}}>
          {isArchived && <Badge variant="blue">ARCHIVÉ</Badge>}
          <span className="db-key-hint" title={db.key_identifier || ''}>{db.key_identifier ? db.key_identifier.slice(0,10)+'…' : ''}</span>
          <ContextMenu trigger={<IconButton>{Icons.more}</IconButton>}>
            <button onClick={()=>onEdit(db)}>{Icons.edit} Modifier</button>
            <button onClick={()=>onExportXml(db)}>{Icons.file} Exporter XML</button>
            <button onClick={()=>onExportSql(db)}>{Icons.download} Exporter SQL</button>
            <hr/>
            {isArchived ? (
              <button onClick={()=>onRestore(db)}>{Icons.upload} Restaurer</button>
            ) : (
              <button onClick={()=>onArchive(db)}>{Icons.download} Archiver</button>
            )}
            <button className="danger" onClick={()=>onDelete(db)}>{Icons.trash} Supprimer</button>
          </ContextMenu>
        </div>
      </div>
      <h3>{db.name} {db.status==='ARCHIVED' && <span style={{fontSize:10, color:'var(--text-tertiary)'}}>ARCHIVÉ</span>}</h3>
      <div className="meta">
        <span>{db.tables_count ?? db.tables ?? 0} tables</span>
        <span className="dim">·</span>
        <span className="dim">{db.creator_name || '—'}</span>
      </div>
      {db.description && <div className="db-desc">{db.description}</div>}
      {db.comment && <div className="db-comment">💬 {db.comment}</div>}
      <div className="db-meta-row">
        <span className="dim">Modifié {db.last_modified_by ? `par ${db.last_modified_by}` : ''} {db.updated_at ? new Date(db.updated_at).toLocaleDateString() : db.updated || ''}</span>
        <span className={`status-dot ${db.status==='ARCHIVED' ? 'archived' : 'active'}`} />
      </div>
      <div className="db-card-footer">
        <div className="db-card-badges">
          <Badge variant={isArchived ? 'blue' : 'green'} dot={isArchived ? '#A0AEC0' : '#22C55E'}>{db.status || 'ACTIVE'}</Badge>
          {db.last_modified_by && <span className="last-user">par {db.last_modified_by}</span>}
        </div>
        <button className="db-card-open" onClick={()=>onOpen(db.name, db.id)}>
          Ouvrir {Icons.arrowRight}
        </button>
      </div>
    </div>
  )
}

export function Dashboard(){
  const navigate = useNavigate()
  const { notify } = useToast()
  const { databases, loading, filteredDbs, createDatabase, updateDatabase, deleteDatabase, archiveDatabase, restoreDatabase, fetchDatabases } = useDatabases()
  const [query, setQuery] = useState('')
  const [showNewDb, setShowNewDb] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [showEditDb, setShowEditDb] = useState(null)
  const [newDbName, setNewDbName] = useState('')
  const [newDbDesc, setNewDbDesc] = useState('')
  const [newDbComment, setNewDbComment] = useState('')
  const [editForm, setEditForm] = useState({ name:'', description:'', comment:'' })
  const [dragOver, setDragOver] = useState(false)
  const [importing, setImporting] = useState(false)

  const list = filteredDbs(query)

  const handleCreate = async ()=>{
    if(!newDbName.trim()){
      notify('error','Nom requis','Entrez un nom de base')
      return
    }
    try{
      await createDatabase({ name: newDbName.trim(), description: newDbDesc.trim(), comment: newDbComment.trim() })
      setNewDbName(''); setNewDbDesc(''); setNewDbComment('')
      setShowNewDb(false)
    }catch{}
  }

  const handleEditOpen = (db)=>{
    setEditForm({ name: db.name, description: db.description || '', comment: db.comment || '' })
    setShowEditDb(db)
  }

  const handleEditSave = async ()=>{
    if(!showEditDb) return
    try{
      await updateDatabase(showEditDb.id, editForm)
      setShowEditDb(null)
      notify('success','Base mise à jour',`« ${editForm.name} » modifiée.`)
    }catch(err){
      notify('error','Erreur', err.message)
    }
  }

  const handleDelete = async (db)=>{
    if(!confirm(`Supprimer la base "${db.name}" ? Cette action est irréversible.`)) return
    try{
      await deleteDatabase(db.id)
      notify('success','Base supprimée',`« ${db.name} » supprimée.`)
    }catch(err){
      notify('error','Erreur suppression', err.message)
    }
  }

  const handleArchive = async (db)=>{
    try{
      await archiveDatabase(db.id)
      notify('success','Base archivée',`« ${db.name} » archivée.`)
    }catch(err){ notify('error','Erreur', err.message) }
  }

  const handleRestore = async (db)=>{
    try{
      await restoreDatabase(db.id)
      notify('success','Base restaurée',`« ${db.name} » restaurée.`)
    }catch(err){ notify('error','Erreur', err.message) }
  }

  const handleExportXml = async (db)=>{
    try{
      await exportService.exportXml(db.id, {download:true})
      notify('success','Export XML',`XML de ${db.name} téléchargé.`)
    }catch(err){ notify('error','Erreur export', err.message) }
  }

  const handleExportSql = async (db)=>{
    try{
      await exportService.exportSql(db.id, {download:true})
      notify('success','Export SQL',`SQL de ${db.name} téléchargé.`)
    }catch(err){ notify('error','Erreur export', err.message) }
  }

  const handleFileDrop = async (e, type='xml')=>{
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer?.files?.[0] || e.target?.files?.[0]
    if(!file) return
    setImporting(true)
    try{
      if(type==='xml'){
        await importService.importXml(file)
      }else{
        await importService.importSql(file)
      }
      notify('success','Import réussi',`${file.name} importé.`)
      fetchDatabases()
      setShowImport(false)
    }catch(err){
      notify('error','Erreur import', err.message)
    }finally{
      setImporting(false)
    }
  }

  return (
    <div className="screen-dashboard">
      <Sidebar onSettings={()=>notify('info','Paramètres','Bientôt disponible.')} />

      <div className="dash-main">
        <Navbar searchValue={query} onSearchChange={setQuery} />

        <div className="dash-content">
          <div className="dash-head">
            <div>
              <h1>Mes bases de données</h1>
              <p>{databases.length} bases de données · {databases.filter(d=>d.status==='ARCHIVED').length} archivées · temps réel via SocketIO</p>
            </div>
            <div className="dash-actions">
              <Button leftIcon={Icons.upload} onClick={()=>setShowImport(true)}>Importer XML / SQL</Button>
              <Button variant="primary" leftIcon={Icons.plus} onClick={()=>setShowNewDb(true)}>Nouvelle base</Button>
            </div>
          </div>

          {loading ? (
            <div className="db-grid">
              {Array.from({length:6}).map((_,i)=><SkeletonCard key={i} />)}
            </div>
          ) : list.length===0 ? (
            <EmptyState
              icon={Icons.db}
              title={query ? "Aucune base ne correspond" : "Aucune base de données"}
              description={query ? `Aucun résultat pour "${query}"` : "Créez votre première base ou importez un XML/SQL"}
              action={<Button variant="primary" leftIcon={Icons.plus} onClick={()=>setShowNewDb(true)}>Nouvelle base</Button>}
            />
          ) : (
            <div className="db-grid">
              {list.map((db,i)=>(
                <DatabaseCard
                  key={db.id}
                  db={db}
                  index={i}
                  onOpen={(name,id)=>navigate(`/workspace/${encodeURIComponent(name)}?dbId=${id}`)}
                  onEdit={handleEditOpen}
                  onDelete={handleDelete}
                  onArchive={handleArchive}
                  onRestore={handleRestore}
                  onExportXml={handleExportXml}
                  onExportSql={handleExportSql}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <Modal open={showImport} onClose={()=>setShowImport(false)} title="Importer XML / SQL" icon={Icons.upload}
        footer={<><Button onClick={()=>setShowImport(false)}>Fermer</Button></>}
      >
        <p className="desc">Glissez-déposez un fichier XML ou SQL, ou sélectionnez un fichier. La structure sera automatiquement créée.</p>
        <div className="grid-2">
          <div
            className={`dropzone ${dragOver ? 'dragover' : ''}`}
            onDragOver={(e)=>{e.preventDefault(); setDragOver(true)}}
            onDragLeave={()=>setDragOver(false)}
            onDrop={(e)=>handleFileDrop(e,'xml')}
            onClick={()=>document.getElementById('xml-file-input')?.click()}
          >
            {Icons.file}
            <div><b>Importer XML</b><br/>Cliquez ou glissez fichier .xml</div>
            <input id="xml-file-input" type="file" accept=".xml" style={{display:'none'}} onChange={(e)=>handleFileDrop(e,'xml')} />
          </div>
          <div
            className={`dropzone ${dragOver ? 'dragover' : ''}`}
            onDragOver={(e)=>{e.preventDefault(); setDragOver(true)}}
            onDragLeave={()=>setDragOver(false)}
            onDrop={(e)=>handleFileDrop(e,'sql')}
            onClick={()=>document.getElementById('sql-file-input')?.click()}
          >
            {Icons.db}
            <div><b>Importer SQL</b><br/>Cliquez ou glissez fichier .sql</div>
            <input id="sql-file-input" type="file" accept=".sql" style={{display:'none'}} onChange={(e)=>handleFileDrop(e,'sql')} />
          </div>
        </div>
        {importing && <div style={{marginTop:12, textAlign:'center'}}><span className="dim">Importation en cours...</span></div>}
      </Modal>

      <Modal open={showNewDb} onClose={()=>setShowNewDb(false)} title="Nouvelle base de données" icon={Icons.db}
        footer={<><Button onClick={()=>setShowNewDb(false)}>Annuler</Button><Button variant="primary" onClick={handleCreate}>Créer la base</Button></>}
      >
        <div className="field-block">
          <label className="form-label">Nom de la base *</label>
          <input className="form-input" placeholder="ex. Bibliothèque, Hôtel, E-commerce..." value={newDbName} onChange={e=>setNewDbName(e.target.value)} />
        </div>
        <div className="field-block">
          <label className="form-label">Description</label>
          <input className="form-input" placeholder="Brève description du projet" value={newDbDesc} onChange={e=>setNewDbDesc(e.target.value)} />
        </div>
        <div className="field-block">
          <label className="form-label">Commentaire</label>
          <input className="form-input" placeholder="Commentaire libre (ex: Base critique prod)" value={newDbComment} onChange={e=>setNewDbComment(e.target.value)} />
        </div>
      </Modal>

      <Modal open={!!showEditDb} onClose={()=>setShowEditDb(null)} title="Modifier la base" icon={Icons.edit}
        footer={<><Button onClick={()=>setShowEditDb(null)}>Annuler</Button><Button variant="primary" onClick={handleEditSave}>Enregistrer</Button></>}
      >
        <div className="field-block">
          <label className="form-label">Nom</label>
          <input className="form-input" value={editForm.name} onChange={e=>setEditForm(f=>({...f, name:e.target.value}))} />
        </div>
        <div className="field-block">
          <label className="form-label">Description</label>
          <input className="form-input" value={editForm.description} onChange={e=>setEditForm(f=>({...f, description:e.target.value}))} />
        </div>
        <div className="field-block">
          <label className="form-label">Commentaire</label>
          <textarea className="form-input" rows={3} value={editForm.comment} onChange={e=>setEditForm(f=>({...f, comment:e.target.value}))} placeholder="Commentaire libre..." />
        </div>
      </Modal>
    </div>
  )
}
