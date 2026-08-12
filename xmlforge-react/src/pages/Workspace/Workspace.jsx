import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useToast } from '../../components/Toast/Toast'
import { useDatabaseContext } from '../../context/DatabaseContext'
import { tableService } from '../../services/tableService'
import { columnService } from '../../services/columnService'
import { databaseService } from '../../services/databaseService'
import { converterService } from '../../services/converterService'
import { exportService } from '../../services/exportService'
import { syncService } from '../../services/syncService'
import { rowService } from '../../services/rowService'
import { projectService } from '../../services/projectService'
import { MonacoEditor } from '../../components/MonacoEditor/MonacoEditor'
import apiClient from '../../services/api'
import { socketService } from '../../services/socketService'

export function Workspace() {
  const { dbName } = useParams()
  const [searchParams] = useSearchParams()
  const dbId = searchParams.get('dbId')
  const navigate = useNavigate()
  const { notify } = useToast()
  const { dbKey, saveKey, saveUnlock, getUnlock } = useDatabaseContext()

  const [database, setDatabase] = useState(null)
  const [tables, setTables] = useState([])
  const [currentTable, setCurrentTable] = useState(null)
  const [columns, setColumns] = useState([])
  const [rows, setRows] = useState([])
  const [rowsTotal, setRowsTotal] = useState(0)
  const [tab, setTab] = useState('structure')

  // Modals
  const [showImport, setShowImport] = useState(false)
  const [showNewTable, setShowNewTable] = useState(false)
  const [showEditCol, setShowEditCol] = useState(null)
  const [showDeleteTable, setShowDeleteTable] = useState(false)
  const [showUnlock, setShowUnlock] = useState(null)
  const [showProtect, setShowProtect] = useState(false)
  const [showRowModal, setShowRowModal] = useState(null) // null or 'new' or row object
  const [showImportProject, setShowImportProject] = useState(false)

  // Forms
  const [newTableForm, setNewTableForm] = useState({ name: '', protected: false, key: '' })
  const [colForm, setColForm] = useState({ name: '', type: 'VARCHAR', length: '255', default: '', nullable: true, primary_key: false, unique: false, auto_increment: false })
  const [unlockKey, setUnlockKey] = useState('')
  const [protectKey, setProtectKey] = useState('')
  const [rowForm, setRowForm] = useState({})
  const [dragOver, setDragOver] = useState(false)
  const [importing, setImporting] = useState(false)

  // Editors
  const [xmlCode, setXmlCode] = useState('')
  const [sqlCode, setSqlCode] = useState('-- Sélectionnez une table')
  const [converting, setConverting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [xmlLoading, setXmlLoading] = useState(false)
  const [xmlError, setXmlError] = useState(null)

  const fileInputRef = useRef(null)
  const projectFileRef = useRef(null)

  const fetchDatabase = useCallback(async () => {
    if (!dbId) return
    try {
      const data = await databaseService.get(dbId)
      setDatabase(data)
    } catch (err) {
      notify('error', 'Erreur base', err.message)
    }
  }, [dbId, notify])

  const fetchTables = useCallback(async () => {
    if (!dbId) return
    try {
      const data = await tableService.list(dbId, true)
      setTables(data)
      if (data.length && !currentTable) {
        setCurrentTable(data[0])
      } else if (currentTable) {
        const upd = data.find(t => t.id === currentTable.id)
        if (upd) setCurrentTable(upd)
      }
    } catch (err) {
      notify('error', 'Erreur tables', err.message)
    }
  }, [dbId, notify])

  const fetchColumns = useCallback(async (tableId) => {
    if (!tableId) return
    try {
      const data = await columnService.list(tableId, true)
      setColumns(data)
    } catch (err) {
      notify('error', 'Erreur colonnes', err.message)
    }
  }, [notify])

  const fetchRows = useCallback(async (tableId) => {
    if (!tableId) return
    try {
      const res = await rowService.list(tableId, { limit: 200 })
      setRows(res.rows || [])
      setRowsTotal(res.total || 0)
    } catch (err) {
      // Si table protégée sans unlock, ne pas afficher erreur bloquante
      if (err.status !== 403) {
        notify('error', 'Erreur données', err.message)
      }
      setRows([])
    }
  }, [notify])

  const fetchTableXml = useCallback(async (table) => {
    if (!table?.id) return
    setXmlLoading(true)
    setXmlError(null)
    try {
      const res = await tableService.getXml(table.id)
      setXmlCode(res.xml || '')
      try {
        const sqlRes = await tableService.getSql(table.id)
        setSqlCode(sqlRes.sql || '-- Aucun SQL')
      } catch {
        setSqlCode('-- Erreur génération SQL')
      }
    } catch (err) {
      const fallback = `<table name="${table.name}" protected="${table.is_protected}"${table.file_identifier ? ` file_identifier="${table.file_identifier}"` : ''}>\n  <columns>\n${columns.map(c => `    <column name="${c.name}" type="${c.type}" length="${c.length}" nullable="${c.nullable}" primary_key="${c.primary_key}" unique="${c.unique}" auto_increment="${c.auto_increment}" />`).join('\n')}\n  </columns>\n  <rows>\n  </rows>\n</table>`
      setXmlCode(fallback)
      setSqlCode('-- Erreur chargement XML')
    } finally {
      setXmlLoading(false)
    }
  }, [columns])

  useEffect(() => { fetchDatabase() }, [fetchDatabase])
  useEffect(() => { fetchTables() }, [dbId])
  useEffect(() => {
    if (currentTable?.id) {
      fetchColumns(currentTable.id)
      fetchRows(currentTable.id)
    }
  }, [currentTable?.id])
  useEffect(() => {
    if (currentTable) fetchTableXml(currentTable)
  }, [currentTable?.id])

  // Monaco XML validation
  useEffect(() => {
    if (!xmlCode) { setXmlError(null); return }
    try {
      const parser = new DOMParser()
      const doc = parser.parseFromString(xmlCode, 'text/xml')
      const err = doc.getElementsByTagName('parsererror')
      if (err.length > 0) {
        // Extract error message
        const msg = err[0].textContent?.slice(0, 200) || 'XML invalide'
        setXmlError(msg)
      } else {
        setXmlError(null)
      }
    } catch (e) {
      setXmlError(e.message)
    }
  }, [xmlCode])

  useEffect(() => {
    socketService.connect()
    const unsubNew = socketService.on('new_table', (payload) => {
      if (payload?.table?.database_id === Number(dbId)) {
        notify('info', 'Nouvelle table', `${payload.by} a créé ${payload.table.name}`)
        fetchTables()
      }
    })
    const unsubMod = socketService.on('modification', () => {
      fetchTables()
      if (currentTable?.id) {
        fetchColumns(currentTable.id)
        fetchRows(currentTable.id)
      }
      fetchDatabase()
    })
    const unsubDel = socketService.on('suppression', () => fetchTables())
    return () => { unsubNew(); unsubMod(); unsubDel() }
  }, [dbId, currentTable?.id])

  const getTableKey = useCallback((table) => {
    if (!table) return null
    return getUnlock(table.id) || dbKey || apiClient.getDbKey()
  }, [dbKey, getUnlock])

  const requireKeyIfProtected = useCallback((table) => {
    if (!table?.is_protected) return true
    const key = getTableKey(table)
    if (!key) {
      setShowUnlock(table)
      return false
    }
    // Vérifier aussi backend personal unlock, mais si key fournie on tentera
    return true
  }, [getTableKey])

  const handleSelectTable = (table) => setCurrentTable(table)

  const handleCreateTable = async () => {
    const name = newTableForm.name.trim()
    if (!name) { notify('error', 'Nom requis', 'Veuillez saisir un nom'); return }
    try {
      const table = await tableService.create({
        name,
        database_id: Number(dbId),
        is_protected: newTableForm.protected,
        file_identifier: newTableForm.key.trim() || null
      })
      setTables(prev => [...prev, table])
      setCurrentTable(table)
      setNewTableForm({ name: '', protected: false, key: '' })
      setShowNewTable(false)
      notify('success', 'Table créée', `« ${name} » ajoutée`)
    } catch (err) {
      notify('error', 'Erreur création', err.message)
    }
  }

  const handleDeleteTable = async () => {
    if (!currentTable) return
    if (!requireKeyIfProtected(currentTable)) return
    try {
      await tableService.delete(currentTable.id, getTableKey(currentTable))
      setTables(prev => prev.filter(t => t.id !== currentTable.id))
      setCurrentTable(null)
      setColumns([])
      setRows([])
      setXmlCode('')
      setSqlCode('-- Table supprimée')
      setShowDeleteTable(false)
      notify('error', 'Table supprimée', `« ${currentTable.name} » supprimée`)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      notify('error', 'Erreur', err.message)
    }
  }

  const handleArchiveToggle = async () => {
    if (!currentTable) return
    if (!requireKeyIfProtected(currentTable)) return
    try {
      const key = getTableKey(currentTable)
      const res = currentTable.status === 'ARCHIVED'
        ? await tableService.restore(currentTable.id, key)
        : await tableService.archive(currentTable.id, key)
      setTables(prev => prev.map(t => t.id === res.id ? res : t))
      setCurrentTable(res)
      notify('success', res.status === 'ARCHIVED' ? 'Archivée' : 'Restaurée', `« ${res.name} » ${res.status === 'ARCHIVED' ? 'archivée' : 'restaurée'}`)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      notify('error', 'Erreur', err.message)
    }
  }

  const handleUnlock = async () => {
    if (!showUnlock) return
    const key = unlockKey.trim()
    if (!key) { notify('error', 'Clé requise', 'Saisissez la clé'); return }
    try {
      await tableService.unlock(showUnlock.id, key)
      saveUnlock(showUnlock.id, key)
      setShowUnlock(null)
      setUnlockKey('')
      notify('success', 'Déverrouillée', `Accès personnel pour « ${showUnlock.name} » (session)`)
      // Refresh to show unlocked state
      fetchColumns(showUnlock.id)
      fetchRows(showUnlock.id)
    } catch (err) {
      notify('error', 'Clé invalide', err.message)
    }
  }

  const handleProtect = async () => {
    if (!currentTable) return
    const key = protectKey.trim()
    if (!key) { notify('error', 'Clé requise', 'Fournissez un code'); return }
    try {
      const updated = await tableService.update(currentTable.id, { is_protected: true, file_identifier: key }, getTableKey(currentTable))
      setTables(prev => prev.map(t => t.id === updated.id ? updated : t))
      setCurrentTable(updated)
      setShowProtect(false)
      setProtectKey('')
      notify('success', 'Protégée', `« ${updated.name} » protégée`)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
  }

  const handleCreateColumn = async () => {
    if (!currentTable) return
    if (!requireKeyIfProtected(currentTable)) return
    if (!colForm.name.trim()) { notify('error', 'Nom requis', ''); return }
    try {
      const payload = {
        name: colForm.name.trim(),
        type: colForm.type,
        length: colForm.length || '-',
        nullable: colForm.nullable,
        primary_key: colForm.primary_key,
        foreign_key: false,
        unique: colForm.unique,
        auto_increment: colForm.auto_increment,
        default: colForm.default || null,
        table_id: currentTable.id
      }
      const key = getTableKey(currentTable)
      if (showEditCol && typeof showEditCol === 'object' && showEditCol.id) {
        const upd = await columnService.update(showEditCol.id, payload, key)
        setColumns(prev => prev.map(c => c.id === upd.id ? upd : c))
        notify('success', 'Colonne mise à jour', '')
      } else {
        const created = await columnService.create(payload, key)
        setColumns(prev => [...prev, created])
        notify('success', 'Colonne créée', '')
      }
      setShowEditCol(null)
      setColForm({ name: '', type: 'VARCHAR', length: '255', default: '', nullable: true, primary_key: false, unique: false, auto_increment: false })
      fetchTableXml(currentTable)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      notify('error', 'Erreur colonne', err.message)
    }
  }

  const handleDeleteColumn = async (col) => {
    if (!currentTable) return
    if (!requireKeyIfProtected(currentTable)) return
    if (!window.confirm(`Supprimer colonne « ${col.name} » ?`)) return
    try {
      await columnService.delete(col.id, getTableKey(currentTable))
      setColumns(prev => prev.filter(c => c.id !== col.id))
      notify('error', 'Colonne supprimée', '')
      fetchTableXml(currentTable)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      notify('error', 'Erreur', err.message)
    }
  }

  const handleConvertXmlToSql = async () => {
    setConverting(true)
    try {
      const res = await converterService.xmlToSql(xmlCode, database?.name)
      setSqlCode(res.sql)
      notify('success', 'Conversion', 'XML → SQL')
    } catch (err) {
      notify('error', 'Erreur conversion', err.message)
      setSqlCode(`-- Erreur: ${err.message}`)
    } finally { setConverting(false) }
  }

  const handleConvertSqlToXml = async () => {
    setConverting(true)
    try {
      const res = await converterService.sqlToXml(sqlCode, database?.name)
      setXmlCode(res.xml)
      notify('success', 'Conversion', 'SQL → XML')
    } catch (err) {
      notify('error', 'Erreur', err.message)
    } finally { setConverting(false) }
  }

  const handleApplyChanges = async () => {
    if (!currentTable) { notify('error', 'Aucune table', ''); return }
    if (!requireKeyIfProtected(currentTable)) return
    if (xmlError) {
      notify('error', 'XML invalide', xmlError)
      return
    }
    setSyncing(true)
    try {
      const key = getTableKey(currentTable)
      const result = await tableService.syncXml(currentTable.id, xmlCode, key)
      if (result.sql) setSqlCode(result.sql)
      if (result.xml) setXmlCode(result.xml)
      await fetchTables()
      await fetchColumns(currentTable.id)
      await fetchRows(currentTable.id)
      await fetchDatabase()
      if (result.table) setCurrentTable(result.table)
      notify('success', 'Modifications appliquées', `${result.created_columns||0} col créées, ${result.updated_columns||0} maj, ${result.deleted_columns||0} suppr.`)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      notify('error', 'Erreur sync', err.message)
    } finally { setSyncing(false) }
  }

  const handleCopy = async (text) => {
    try { await navigator.clipboard.writeText(text); notify('success', 'Copié', '') } catch { notify('error', 'Erreur', '') }
  }
  const handleDownload = (content, filename) => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
    notify('success', 'Téléchargé', filename)
  }

  const handleImportXmlInWorkspace = async (file) => {
    if (!file) return
    setImporting(true)
    try {
      const text = await file.text()
      await syncService.syncDatabase(dbId, text, getTableKey(currentTable))
      await fetchTables()
      await fetchDatabase()
      setShowImport(false)
      notify('success', 'Import réussi', 'Base synchronisée')
    } catch (err) {
      notify('error', 'Erreur import', err.message)
    } finally { setImporting(false) }
  }

  const handleExportProject = async () => {
    try {
      await projectService.exportProject(dbId, { download: true })
      notify('success', 'Projet exporté', 'Fichier complet avec données, protections, file_identifier')
    } catch (err) {
      notify('error', 'Erreur export projet', err.message)
    }
  }

  const handleImportProject = async (file) => {
    if (!file) return
    setImporting(true)
    try {
      const db = await projectService.importProject(file)
      notify('success', 'Projet importé', `Base « ${db.name} » reconstruite avec tables, colonnes, données`)
      navigate(`/workspace/${encodeURIComponent(db.name)}?dbId=${db.id}`)
    } catch (err) {
      notify('error', 'Erreur import projet', err.message)
    } finally {
      setImporting(false)
      setShowImportProject(false)
    }
  }

  // Row handling
  const openNewRow = () => {
    if (!currentTable) return
    if (!requireKeyIfProtected(currentTable)) return
    const init = {}
    columns.forEach(c => { init[c.name] = '' })
    setRowForm(init)
    setShowRowModal('new')
  }

  const openEditRow = (row) => {
    if (!requireKeyIfProtected(currentTable)) return
    setRowForm({ ...row.data })
    setShowRowModal(row)
  }

  const handleSaveRow = async () => {
    if (!currentTable) return
    const key = getTableKey(currentTable)
    try {
      if (showRowModal === 'new') {
        await rowService.create(currentTable.id, rowForm, key)
        notify('success', 'Ligne ajoutée', '')
      } else {
        await rowService.update(currentTable.id, showRowModal.id, rowForm, key)
        notify('success', 'Ligne modifiée', '')
      }
      setShowRowModal(null)
      fetchRows(currentTable.id)
      fetchTableXml(currentTable)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      notify('error', 'Erreur ligne', err.message)
    }
  }

  const handleDeleteRow = async (row) => {
    if (!currentTable) return
    if (!requireKeyIfProtected(currentTable)) return
    if (!window.confirm(`Supprimer ligne #${row.id} ?`)) return
    try {
      await rowService.delete(currentTable.id, row.id, getTableKey(currentTable))
      setRows(prev => prev.filter(r => r.id !== row.id))
      notify('error', 'Ligne supprimée', '')
      fetchTableXml(currentTable)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      notify('error', 'Erreur', err.message)
    }
  }

  const boolChip = (v) => v
    ? <span className="chip yes"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg></span>
    : <span className="chip no">—</span>

  if (!dbId) {
    return (
      <div className="screen active" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="empty-state">
          <div className="es-title">Aucune base sélectionnée</div>
          <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>Retour Dashboard</button>
        </div>
      </div>
    )
  }

  return (
    <div className="screen active" id="screen-workspace">
      <div className="ws-titlebar">
        <a className="back-btn" href="#" onClick={(e) => { e.preventDefault(); navigate('/dashboard') }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
          Bases
        </a>
        <div className="ws-crumb">/ <b>{database?.name || dbName}</b> / <span>{currentTable?.name || '—'}</span></div>
        <span className={`badge ${database?.status === 'ARCHIVED' ? 'badge-gray' : 'badge-green'}`}><span className="badge-dot" style={{ background: database?.status === 'ARCHIVED' ? '#A0AEC0' : '#22C55E' }}></span>{database?.status || 'ACTIF'}</span>
        <div className="ws-titlebar-right">
          <span className="badge badge-blue"><span className="badge-dot" style={{ background: '#3B82F6' }}></span>XML synchronisé</span>
          <button className="btn btn-sm" onClick={handleExportProject} title="Exporter projet complet avec données, protections, file_identifier">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
            Projet
          </button>
          <button className="btn btn-sm btn-primary" onClick={async () => {
            try { await exportService.exportSql(dbId, { download: true }); notify('success', 'Export SQL', '') } catch (err) { notify('error', 'Erreur', err.message) }
          }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
            Exporter SQL
          </button>
        </div>
      </div>

      <div className="ws-body">
        <aside className="ws-sidebar">
          <div className="ws-sidebar-head">Tables</div>
          <div className="ws-table-list">
            {tables.map(t => {
              const isActive = currentTable?.id === t.id
              const unlocked = !t.is_protected || getTableKey(t)
              return (
                <a key={t.id} className={`ws-table-item ${isActive ? 'active' : ''}`} href="#" onClick={(e) => { e.preventDefault(); handleSelectTable(t) }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
                  <span className="name-wrap"><span>{t.name}</span>{t.is_protected && <span className={`lock-ic ${unlocked ? 'unlocked' : ''}`}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{unlocked ? <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.5-2"/></> : <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>}</svg></span>}</span>
                  {t.status === 'ARCHIVED' && <span className="arch-tag">ARCH</span>}
                  <span className="count">{t.columns_count || ''}</span>
                </a>
              )
            })}
            {tables.length === 0 && <div className="empty-state" style={{ padding: '20px' }}><div className="es-title" style={{ fontSize: '12px' }}>Aucune table</div></div>}
          </div>
          <div className="ws-sidebar-actions">
            <button className="btn btn-sm" onClick={() => setShowNewTable(true)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14"/></svg>
              Nouvelle table
            </button>
            <button className="btn btn-sm" onClick={() => setShowImport(true)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
              Importer XML
            </button>
            <button className="btn btn-sm" onClick={() => setShowImportProject(true)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M12 18v-6M9 15l3 3 3-3"/></svg>
              Importer projet
            </button>
            <button className="btn btn-sm" onClick={handleExportProject}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
              Exporter projet
            </button>
          </div>
        </aside>

        <main className="ws-main">
          <div className="ws-main-head">
            <div className="ws-main-head-left">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              <div>
                <h2>{currentTable?.name || 'Aucune table'}{currentTable?.is_protected ? <span style={{ marginLeft: '8px', color: 'var(--warn)', display: 'inline-flex' }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></span> : ''}</h2>
                <div className="sub">{currentTable ? `${columns.length} colonnes · ${rowsTotal} lignes · clé primaire : ${columns.find(c => c.primary_key)?.name || '—'} · statut : ${currentTable.status === 'ARCHIVED' ? 'archivée' : 'active'}` : 'Sélectionnez une table'}</div>
              </div>
            </div>
            <div className="ws-main-actions">
              <button className="btn btn-sm" onClick={() => {
                if (!currentTable) { notify('error', 'Aucune table', ''); return }
                if (!requireKeyIfProtected(currentTable)) return
                setColForm({ name: '', type: 'VARCHAR', length: '255', default: '', nullable: true, primary_key: false, unique: false, auto_increment: false })
                setShowEditCol('new')
              }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Colonne
              </button>
              <button className="btn btn-sm" onClick={openNewRow}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Ligne
              </button>
              <button className="btn btn-sm" onClick={handleArchiveToggle}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8"/><path d="M10 12h4"/></svg>
                <span>{currentTable?.status === 'ARCHIVED' ? 'Restaurer' : 'Archiver'}</span>
              </button>
              <button className="btn btn-sm btn-danger" onClick={() => {
                if (!currentTable) return
                if (!requireKeyIfProtected(currentTable)) return
                setShowDeleteTable(true)
              }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
                Supprimer
              </button>
              {currentTable && !currentTable.is_protected && (
                <button className="btn btn-sm" onClick={() => setShowProtect(true)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  Protéger
                </button>
              )}
            </div>
          </div>

          <div className="tabs-row">
            <div className="tabs-seg">
              <button className={`tab-btn ${tab === 'structure' ? 'active' : ''}`} onClick={() => setTab('structure')}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
                Structure
              </button>
              <button className={`tab-btn ${tab === 'data' ? 'active' : ''}`} onClick={() => setTab('data')}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
                Données {rowsTotal > 0 ? `(${rowsTotal})` : ''}
              </button>
            </div>
          </div>

          <div className={`tab-panel ${tab === 'structure' ? 'active' : ''}`}>
            <div className="table-wrap">
              <table className="cols-table">
                <thead>
                  <tr>
                    <th>Nom</th><th>Type</th><th>Longueur</th><th>Nullable</th><th>PK</th><th>FK</th><th>Unique</th><th>Auto Inc.</th><th>État</th><th>Modifié par</th><th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {columns.map(c => (
                    <tr key={c.id}>
                      <td className="col-name">{c.name}</td>
                      <td className="col-type">{c.type}</td>
                      <td>{c.length}</td>
                      <td>{boolChip(c.nullable)}</td>
                      <td>{c.primary_key ? <span className="pk-tag">PK</span> : boolChip(false)}</td>
                      <td>{c.foreign_key ? <span className="fk-tag">FK</span> : boolChip(false)}</td>
                      <td>{boolChip(c.unique)}</td>
                      <td>{boolChip(c.auto_increment)}</td>
                      <td><span className="badge badge-green" style={{ padding: '2px 8px' }}>{c.status || 'ACTIF'}</span></td>
                      <td style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{c.last_modified_by || '—'}</td>
                      <td>
                        <div className="row-actions">
                          <button className="icon-btn sm" title="Modifier" onClick={() => {
                            if (!requireKeyIfProtected(currentTable)) return
                            setColForm({
                              name: c.name,
                              type: c.type,
                              length: c.length,
                              default: c.default || '',
                              nullable: c.nullable,
                              primary_key: c.primary_key,
                              unique: c.unique,
                              auto_increment: c.auto_increment
                            })
                            setShowEditCol(c)
                          }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                          </button>
                          <button className="icon-btn sm danger" title="Supprimer" onClick={() => handleDeleteColumn(c)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {columns.length === 0 && (
                    <tr><td colSpan={11}><div className="empty-state" style={{ padding: '30px' }}><div className="es-title">Aucune colonne</div><div className="es-desc">Ajoutez votre première colonne.</div></div></td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className={`tab-panel ${tab === 'data' ? 'active' : ''}`}>
            <div className="table-wrap">
              {columns.length === 0 ? (
                <div className="empty-state" style={{ padding: '40px' }}>
                  <div className="es-title">Aucune colonne définie</div>
                  <div className="es-desc">Créez d'abord des colonnes dans l'onglet Structure pour pouvoir gérer les données.</div>
                </div>
              ) : (
                <table className="cols-table">
                  <thead>
                    <tr>
                      {columns.map(col => <th key={col.id}>{col.name}</th>)}
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(row => (
                      <tr key={row.id}>
                        {columns.map(col => (
                          <td key={col.id} style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                            {row.data[col.name] !== undefined ? String(row.data[col.name]) : <span style={{ color: 'var(--text-tertiary)' }}>—</span>}
                          </td>
                        ))}
                        <td>
                          <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                            <button className="icon-btn sm" title="Modifier" onClick={() => openEditRow(row)}>
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                            </button>
                            <button className="icon-btn sm danger" title="Supprimer" onClick={() => handleDeleteRow(row)}>
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {rows.length === 0 && (
                      <tr><td colSpan={columns.length + 1}><div className="empty-state" style={{ padding: '30px' }}><div className="es-title">Aucune donnée</div><div className="es-desc">Ajoutez votre première ligne. Les données sont stockées dans XMLForge et exportées dans le XML.</div><button className="btn btn-sm btn-primary" style={{ marginTop: '10px' }} onClick={openNewRow}>+ Ajouter une ligne</button></div></td></tr>
                    )}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </main>

        <aside className="ws-right">
          <div className="code-pane" id="pane-xml">
            <div className="code-pane-head">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
              XML Source
              <span className="lang-badge">XML</span>
              {xmlError && <span className="badge badge-red" title={xmlError}>Erreur XML</span>}
              <div className="code-pane-head-actions">
                <button className="icon-btn sm" title="Copier" onClick={() => handleCopy(xmlCode)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
                <button className="icon-btn sm" title="Télécharger" onClick={() => handleDownload(xmlCode, `${currentTable?.name || 'table'}.xml`)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg></button>
              </div>
            </div>
            <div className="code-pane-body" style={{ padding: 0, display: 'flex', flexDirection: 'column', minHeight: '240px' }}>
              {xmlLoading ? (
                <div style={{ padding: '20px', color: 'var(--text-tertiary)', fontSize: '12px' }}>Chargement XML...</div>
              ) : (
                <MonacoEditor value={xmlCode} onChange={setXmlCode} language="xml" />
              )}
            </div>
            {xmlError && <div style={{ padding: '6px 12px', fontSize: '11px', color: '#FF8787', background: 'var(--danger-soft)', borderTop: '1px solid #EF444440' }}>⚠ {xmlError.slice(0, 200)}</div>}
          </div>

          <div className="apply-row">
            <button className="btn btn-sm btn-block" onClick={handleConvertXmlToSql} disabled={converting}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M19 12l-7 7-7-7"/></svg>
              {converting ? 'Conversion...' : 'Convertir XML → SQL'}
            </button>
            <button className="btn btn-sm btn-primary btn-block" onClick={handleApplyChanges} disabled={syncing}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
              {syncing ? 'Synchronisation...' : 'Appliquer les modifications'}
            </button>
            <div className="apply-hint">POST /tables/{'{id}'}/sync-xml · personnel par utilisateur</div>
          </div>

          <div className="code-pane" id="pane-sql">
            <div className="code-pane-head">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
              SQL généré
              <span className="lang-badge">SQL</span>
              <div className="code-pane-head-actions">
                <button className="icon-btn sm" title="↑ SQL → XML" onClick={handleConvertSqlToXml}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>
                <button className="icon-btn sm" title="Copier" onClick={() => handleCopy(sqlCode)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
                <button className="icon-btn sm" title="Télécharger" onClick={() => handleDownload(sqlCode, `${currentTable?.name || 'table'}.sql`)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg></button>
              </div>
            </div>
            <div className="code-pane-body" style={{ padding: 0, display: 'flex', flexDirection: 'column', minHeight: '200px' }}>
              <MonacoEditor value={sqlCode} onChange={setSqlCode} language="sql" />
            </div>
          </div>
        </aside>
      </div>

      {/* Modals */}
      <div className={`modal-overlay ${showImport ? 'open' : ''}`} onClick={() => setShowImport(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>Importer XML</h3>
            <button className="icon-btn" onClick={() => setShowImport(false)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <p className="desc">Glissez-déposez un fichier XML pour ajouter des tables à la base actuelle.</p>
            <div className={`dropzone ${dragOver ? 'dragover' : ''}`} onDragEnter={e => { e.preventDefault(); setDragOver(true) }} onDragOver={e => { e.preventDefault(); setDragOver(true) }} onDragLeave={e => { e.preventDefault(); setDragOver(false) }} onDrop={e => { e.preventDefault(); setDragOver(false); const f=e.dataTransfer.files[0]; if(f) handleImportXmlInWorkspace(f)}} onClick={() => fileInputRef.current?.click()}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
              <div><b>Cliquez</b> ou glissez-déposez .xml</div>
            </div>
            <input type="file" ref={fileInputRef} className="hidden" accept=".xml" onChange={e => { const f=e.target.files[0]; if(f) handleImportXmlInWorkspace(f)}} />
            {importing && <div className="import-progress"><span className="mini-spinner"></span>Import...</div>}
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowImport(false)}>Annuler</button>
            <button className="btn btn-primary" onClick={() => fileInputRef.current?.click()}>Importer</button>
          </div>
        </div>
      </div>

      <div className={`modal-overlay ${showImportProject ? 'open' : ''}`} onClick={() => setShowImportProject(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M12 18v-6M9 15l3 3 3-3"/></svg>Importer projet complet</h3>
            <button className="icon-btn" onClick={() => setShowImportProject(false)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <p className="desc">Importe un projet XMLForge complet (base + tables + colonnes + protections + file_identifier + données). Reconstruit automatiquement tout.</p>
            <div className={`dropzone ${dragOver ? 'dragover' : ''}`} onDragEnter={e => { e.preventDefault(); setDragOver(true) }} onDragOver={e => { e.preventDefault(); setDragOver(true) }} onDragLeave={e => { e.preventDefault(); setDragOver(false) }} onDrop={e => { e.preventDefault(); setDragOver(false); const f=e.dataTransfer.files[0]; if(f) handleImportProject(f)}} onClick={() => projectFileRef.current?.click()}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
              <div><b>Projet complet</b> .xml avec données</div>
            </div>
            <input type="file" ref={projectFileRef} className="hidden" accept=".xml" onChange={e => { const f=e.target.files[0]; if(f) handleImportProject(f)}} />
            {importing && <div className="import-progress"><span className="mini-spinner"></span>Import projet...</div>}
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowImportProject(false)}>Annuler</button>
            <button className="btn btn-primary" onClick={() => projectFileRef.current?.click()}>Importer projet</button>
          </div>
        </div>
      </div>

      <div className={`modal-overlay ${showNewTable ? 'open' : ''}`} onClick={() => setShowNewTable(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>Nouvelle table</h3>
            <button className="icon-btn" onClick={() => setShowNewTable(false)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <div className="field-block"><label className="form-label">Nom de la table</label><input className="form-input" type="text" placeholder="ex. commande" value={newTableForm.name} onChange={e => setNewTableForm(f => ({ ...f, name: e.target.value }))} /></div>
            <div className="check-row"><label className="switch"><input type="checkbox" checked={newTableForm.protected} onChange={e => setNewTableForm(f => ({ ...f, protected: e.target.checked }))} /><span className="track"></span></label><label>Table protégée</label></div>
            {newTableForm.protected && (
              <div className="field-block" style={{ marginTop: '10px' }}>
                <label className="form-label">Code de protection</label>
                <input className="form-input" type="text" placeholder="XML-9F4A-2C1B" style={{ fontFamily: 'var(--font-mono)' }} value={newTableForm.key} onChange={e => setNewTableForm(f => ({ ...f, key: e.target.value }))} />
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowNewTable(false)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleCreateTable}>Créer</button>
          </div>
        </div>
      </div>

      <div className={`modal-overlay ${showEditCol ? 'open' : ''}`} onClick={() => setShowEditCol(null)}>
        <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>{showEditCol === 'new' ? 'Ajouter colonne' : 'Modifier colonne'}</h3>
            <button className="icon-btn" onClick={() => setShowEditCol(null)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <div className="grid-2">
              <div className="field-block"><label className="form-label">Nom</label><input className="form-input" value={colForm.name} onChange={e => setColForm(f => ({ ...f, name: e.target.value }))} /></div>
              <div className="field-block"><label className="form-label">Type</label><select className="form-input" value={colForm.type} onChange={e => setColForm(f => ({ ...f, type: e.target.value }))}><option>VARCHAR</option><option>INT</option><option>TEXT</option><option>DATETIME</option><option>DECIMAL</option><option>BOOLEAN</option><option>BIGINT</option></select></div>
            </div>
            <div className="grid-2">
              <div className="field-block"><label className="form-label">Longueur</label><input className="form-input" value={colForm.length} onChange={e => setColForm(f => ({ ...f, length: e.target.value }))} /></div>
              <div className="field-block"><label className="form-label">Défaut</label><input className="form-input" value={colForm.default} onChange={e => setColForm(f => ({ ...f, default: e.target.value }))} /></div>
            </div>
            <div className="grid-2" style={{ marginTop: '4px' }}>
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.nullable} onChange={e => setColForm(f => ({ ...f, nullable: e.target.checked }))} /><span className="track"></span></label><label>Nullable</label></div>
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.primary_key} onChange={e => setColForm(f => ({ ...f, primary_key: e.target.checked }))} /><span className="track"></span></label><label>PK</label></div>
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.unique} onChange={e => setColForm(f => ({ ...f, unique: e.target.checked }))} /><span className="track"></span></label><label>Unique</label></div>
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.auto_increment} onChange={e => setColForm(f => ({ ...f, auto_increment: e.target.checked }))} /><span className="track"></span></label><label>AI</label></div>
            </div>
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowEditCol(null)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleCreateColumn}>Enregistrer</button>
          </div>
        </div>
      </div>

      <div className={`modal-overlay ${showDeleteTable ? 'open' : ''}`} onClick={() => setShowDeleteTable(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4M12 17h.01"/></svg>Supprimer table</h3>
            <button className="icon-btn" onClick={() => setShowDeleteTable(false)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body"><div className="danger-box">Supprimer définitivement <b>{currentTable?.name}</b> ?</div></div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowDeleteTable(false)}>Annuler</button><button className="btn btn-danger" onClick={handleDeleteTable}>Supprimer</button></div>
        </div>
      </div>

      <div className={`modal-overlay ${showUnlock ? 'open' : ''}`} onClick={() => setShowUnlock(null)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>🔒 Table protégée</h3><button className="icon-btn" onClick={() => setShowUnlock(null)}>✕</button></div>
          <div className="modal-body">
            <div className="info-box"><span>Table <b style={{ color: '#fff' }}>{showUnlock?.name}</b> protégée. Déverrouillage <b>personnel</b> (session utilisateur uniquement). Autres utilisateurs devront fournir la clé.</span></div>
            <div className="field-block"><label className="form-label">Clé de protection</label><input className="form-input" style={{ fontFamily: 'var(--font-mono)' }} value={unlockKey} onChange={e => setUnlockKey(e.target.value)} placeholder="XML-..." /></div>
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowUnlock(null)}>Annuler</button><button className="btn btn-primary" onClick={handleUnlock}>Déverrouiller pour moi</button></div>
        </div>
      </div>

      <div className={`modal-overlay ${showProtect ? 'open' : ''}`} onClick={() => setShowProtect(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Protéger table</h3><button className="icon-btn" onClick={() => setShowProtect(false)}>✕</button></div>
          <div className="modal-body"><div className="field-block"><label className="form-label">File Identifier</label><input className="form-input" style={{ fontFamily: 'var(--font-mono)' }} value={protectKey} onChange={e => setProtectKey(e.target.value)} placeholder="XML-..." /></div></div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowProtect(false)}>Annuler</button><button className="btn btn-primary" onClick={handleProtect}>Protéger</button></div>
        </div>
      </div>

      {/* Row Modal */}
      <div className={`modal-overlay ${showRowModal ? 'open' : ''}`} onClick={() => setShowRowModal(null)}>
        <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3>{showRowModal === 'new' ? 'Ajouter une ligne' : 'Modifier la ligne'}</h3>
            <button className="icon-btn" onClick={() => setShowRowModal(null)}>✕</button>
          </div>
          <div className="modal-body">
            {columns.length === 0 ? (
              <div className="empty-state"><div className="es-title">Aucune colonne</div></div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {columns.map(col => (
                  <div key={col.id} className="field-block" style={{ marginBottom: 0 }}>
                    <label className="form-label">{col.name} <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>({col.type})</span></label>
                    <input className="form-input" value={rowForm[col.name] || ''} onChange={e => setRowForm(f => ({ ...f, [col.name]: e.target.value }))} placeholder={col.default || ''} />
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowRowModal(null)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleSaveRow}>Enregistrer</button>
          </div>
        </div>
      </div>
    </div>
  )
}
