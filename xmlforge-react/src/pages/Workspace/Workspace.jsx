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
import { accessService } from '../../services/accessService'
import { MonacoEditor } from '../../components/MonacoEditor/MonacoEditor'
import { ConflictDialog } from '../../components/ConflictDialog/ConflictDialog'
import { socketService } from '../../services/socketService'

const emptyColumnForm = { name: '', type: 'VARCHAR', length: '255', default: '', nullable: true, primary_key: false, foreign_key: false, references: '', unique: false, auto_increment: false, index: false, on_delete: 'NO ACTION', on_update: 'NO ACTION' }

export function Workspace() {
  const { dbName, databaseId } = useParams()
  const [searchParams] = useSearchParams()
  const dbId = databaseId || searchParams.get('dbId')
  const navigate = useNavigate()
  const { notify } = useToast()
  const { markUnlocked, isUnlocked } = useDatabaseContext()

  const [database, setDatabase] = useState(null)
  const [tables, setTables] = useState([])
  const [currentTable, setCurrentTable] = useState(null)
  const [columns, setColumns] = useState([])
  const [rows, setRows] = useState([])
  const [rowsTotal, setRowsTotal] = useState(0)
  const [rowsLoading, setRowsLoading] = useState(false)
  const [rowsError, setRowsError] = useState(null)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [rowSearch, setRowSearch] = useState('')
  const [rowSort, setRowSort] = useState('')
  const [rowOrder, setRowOrder] = useState('ASC')
  const [documentVersion, setDocumentVersion] = useState(null)
  const [relationColumns, setRelationColumns] = useState({})
  const [relationsLoading, setRelationsLoading] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [tab, setTab] = useState('structure')

  // Modals
  const [showImport, setShowImport] = useState(false)
  const [showNewTable, setShowNewTable] = useState(false)
  const [showEditCol, setShowEditCol] = useState(null)
  const [showDeleteTable, setShowDeleteTable] = useState(false)
  const [showUnlock, setShowUnlock] = useState(null)
  const [showProtect, setShowProtect] = useState(false)
  const [showTableAccess, setShowTableAccess] = useState(false)
  const [tablePermissions, setTablePermissions] = useState([])
  const [tableAccessEmail, setTableAccessEmail] = useState('')
  const [tableGrantLevel, setTableGrantLevel] = useState('VIEW')
  const [tableAccessLoading, setTableAccessLoading] = useState(false)
  const [showDbAccess, setShowDbAccess] = useState(false)
  const [dbPermissions, setDbPermissions] = useState([])
  const [dbAccessEmail, setDbAccessEmail] = useState('')
  const [dbGrantLevel, setDbGrantLevel] = useState('VIEW')
  const [dbAccessLoading, setDbAccessLoading] = useState(false)
  const [showRowModal, setShowRowModal] = useState(null) // null or 'new' or row object

  // Forms
  const [newTableForm, setNewTableForm] = useState({ name: '', withId: true, protected: false, key: '' })
  const [colForm, setColForm] = useState(emptyColumnForm)
  const [fkTableId, setFkTableId] = useState('')
  const [fkColumnName, setFkColumnName] = useState('')
  const [fkColumnOptions, setFkColumnOptions] = useState([])
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
  const [fullscreenPane, setFullscreenPane] = useState(null)

  const fileInputRef = useRef(null)

  const fetchDatabase = useCallback(async () => {
    if (!dbId) return
    try {
      const data = await databaseService.get(dbId)
      setDatabase(data)
      setDocumentVersion(data.document_version)
    } catch (err) {
      notify('error', 'Erreur base', err.message)
    }
  }, [dbId, notify])

  const fetchTables = useCallback(async () => {
    if (!dbId) return
    try {
      const data = await tableService.list(dbId, true)
      setTables(data)
      setCurrentTable(previous => {
        if (!data.length) return null
        if (!previous) return data[0]
        return data.find(table => table.id === previous.id) || data[0]
      })
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
    setRowsLoading(true)
    setRowsError(null)
    try {
      const res = await rowService.list(tableId, {
        limit: pageSize,
        offset: (page - 1) * pageSize,
        search: rowSearch.trim(),
        sort: rowSort,
        order: rowOrder,
      })
      setRows(res.rows || [])
      setRowsTotal(res.total || 0)
    } catch (err) {
      setRowsError(err.message)
      setRows([])
      if (err.status !== 403) notify('error', 'Erreur données', err.message)
    } finally {
      setRowsLoading(false)
    }
  }, [notify, page, pageSize, rowSearch, rowSort, rowOrder])

  const fetchTableXml = useCallback(async (table) => {
    if (!table?.id) return
    setXmlLoading(true)
    setXmlError(null)
    try {
      const res = await tableService.getXml(table.id)
      setXmlCode(res.xml || '')
      if (res.document_version != null) setDocumentVersion(res.document_version)
      try {
        const sqlRes = await tableService.getSql(table.id)
        setSqlCode(sqlRes.sql || '-- Aucun SQL')
      } catch {
        setSqlCode('-- Erreur génération SQL')
      }
    } catch (err) {
      setXmlCode('')
      setSqlCode('-- XML indisponible pour votre niveau d’accès')
      setXmlError(err.message)
    } finally {
      setXmlLoading(false)
    }
  }, [])

  useEffect(() => { fetchDatabase() }, [fetchDatabase])
  useEffect(() => { fetchTables() }, [fetchTables])
  useEffect(() => {
    if (currentTable?.id) {
      setPage(1)
      fetchColumns(currentTable.id)
    }
  }, [currentTable?.id, fetchColumns])
  useEffect(() => {
    if (currentTable?.id) fetchRows(currentTable.id)
  }, [currentTable?.id, fetchRows])
  useEffect(() => {
    if (currentTable) fetchTableXml(currentTable)
  }, [currentTable, fetchTableXml])
  useEffect(() => {
    if (tab !== 'relations' || tables.length === 0) return
    let active = true
    setRelationsLoading(true)
    Promise.all(tables.map(async table => [table.name, await columnService.list(table.id, false)]))
      .then(entries => { if (active) setRelationColumns(Object.fromEntries(entries)) })
      .catch(err => notify('error', 'Relations', err.message))
      .finally(() => { if (active) setRelationsLoading(false) })
    return () => { active = false }
  }, [tab, tables, notify])

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
  }, [dbId, currentTable?.id, fetchTables, fetchColumns, fetchRows, fetchDatabase, notify])

  const requireUnlocked = useCallback((table) => {
    if (!table?.is_protected || isUnlocked(table.id)) return true
    setShowUnlock(table)
    return false
  }, [isUnlocked])

  const handleConflict = useCallback((err) => {
    if (!err?.isConflict) return false
    setConflict(true)
    return true
  }, [])

  const handleSelectTable = (table) => setCurrentTable(table)

  const handleCreateTable = async () => {
    const name = newTableForm.name.trim()
    if (!name) { notify('error', 'Nom requis', 'Veuillez saisir un nom'); return }
    if (newTableForm.protected && !newTableForm.key.trim()) { notify('error', 'Code requis', 'Le backend ne génère pas automatiquement le code de protection.'); return }
    try {
      const table = await tableService.create({
        name,
        database_id: Number(dbId),
        is_protected: newTableForm.protected,
        file_identifier: newTableForm.key.trim() || null
      }, documentVersion)
      let latestDatabase = await databaseService.get(dbId)
      if (newTableForm.protected && newTableForm.key.trim()) {
        await tableService.unlock(table.id, newTableForm.key.trim())
        markUnlocked(table.id)
      }
      if (newTableForm.withId) {
        await columnService.create({ name: 'id', type: 'INT', length: '11', nullable: false, primary_key: true, auto_increment: true, unique: false, foreign_key: false, index: false, table_id: table.id }, latestDatabase.document_version)
        latestDatabase = await databaseService.get(dbId)
      }
      setDocumentVersion(latestDatabase.document_version)
      setTables(prev => [...prev, { ...table, columns_count: newTableForm.withId ? 1 : 0 }])
      setCurrentTable({ ...table, columns_count: newTableForm.withId ? 1 : 0 })
      setNewTableForm({ name: '', withId: true, protected: false, key: '' })
      setShowNewTable(false)
      await fetchDatabase()
      notify('success', 'Table créée', `« ${name} » ajoutée`)
    } catch (err) {
      if (!handleConflict(err)) notify('error', 'Erreur création', err.message)
    }
  }

  const handleDeleteTable = async () => {
    if (!currentTable) return
    if (!requireUnlocked(currentTable)) return
    try {
      await tableService.delete(currentTable.id, documentVersion)
      setTables(prev => prev.filter(t => t.id !== currentTable.id))
      setCurrentTable(null)
      setColumns([])
      setRows([])
      setXmlCode('')
      setSqlCode('-- Table supprimée')
      setShowDeleteTable(false)
      await fetchDatabase()
      notify('success', 'Table supprimée', `« ${currentTable.name} » supprimée`)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      if (!handleConflict(err)) notify('error', 'Erreur', err.message)
    }
  }

  const handleArchiveToggle = async () => {
    if (!currentTable) return
    if (!requireUnlocked(currentTable)) return
    try {
      const res = currentTable.status === 'ARCHIVED'
        ? await tableService.restore(currentTable.id)
        : await tableService.archive(currentTable.id)
      const withAccess = { ...res, access: currentTable.access }
      setTables(prev => prev.map(t => t.id === res.id ? withAccess : t))
      setCurrentTable(withAccess)
      await fetchDatabase()
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
      markUnlocked(showUnlock.id)
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
      const updated = await tableService.update(currentTable.id, { is_protected: true, file_identifier: key }, documentVersion)
      setTables(prev => prev.map(t => t.id === updated.id ? updated : t))
      setCurrentTable(updated)
      setShowProtect(false)
      setProtectKey('')
      await fetchDatabase()
      notify('success', 'Protégée', `« ${updated.name} » protégée`)
    } catch (err) {
      if (!handleConflict(err)) notify('error', 'Erreur', err.message)
    }
  }

  const handleUnprotect = async () => {
    if (!currentTable) return
    if (!window.confirm(`Retirer la protection de « ${currentTable.name} » ? Elle restera accessible aux utilisateurs autorisés sans clé.`)) return
    try {
      const updated = await tableService.update(currentTable.id, { is_protected: false, file_identifier: null }, documentVersion)
      setTables(prev => prev.map(t => t.id === updated.id ? updated : t))
      setCurrentTable(prev => ({ ...prev, ...updated, access: prev?.access }))
      await fetchDatabase()
      notify('success', 'Protection retirée', `« ${updated.name} » n'est plus protégée`)
    } catch (err) {
      if (!handleConflict(err)) notify('error', 'Erreur', err.message)
    }
  }

  const openTableAccess = async () => {
    if (!currentTable) return
    setTableAccessEmail('')
    setTableGrantLevel('VIEW')
    setTableAccessLoading(true)
    setShowTableAccess(true)
    try {
      setTablePermissions(await accessService.listTable(currentTable.id))
    } catch (err) {
      notify('error', 'Accès table', err.message)
      setShowTableAccess(false)
    } finally {
      setTableAccessLoading(false)
    }
  }

  const grantTableAccess = async () => {
    if (!currentTable || !tableAccessEmail.trim()) return
    const rights = tableGrantLevel === 'MANAGE'
      ? { can_read: true, can_write: true, can_ddl: true, can_admin: true }
      : tableGrantLevel === 'EDIT'
        ? { can_read: true, can_write: true, can_ddl: true, can_admin: false }
        : { can_read: true, can_write: false, can_ddl: false, can_admin: false }
    try {
      await accessService.grantTable(currentTable.id, { email: tableAccessEmail.trim(), ...rights })
      setTablePermissions(await accessService.listTable(currentTable.id))
      setTableAccessEmail('')
      notify('success', 'Accès table partagé', `${tableGrantLevel} accordé sur « ${currentTable.name} »`)
    } catch (err) { notify('error', 'Partage impossible', err.message) }
  }

  const revokeTableAccess = async (permission) => {
    if (!currentTable) return
    try {
      await accessService.revokeTable(currentTable.id, permission.user_id)
      setTablePermissions(prev => prev.filter(item => item.user_id !== permission.user_id))
    } catch (err) { notify('error', 'Retrait impossible', err.message) }
  }

  const openDbAccess = async () => {
    if (!database) return
    setDbAccessEmail('')
    setDbGrantLevel('VIEW')
    setDbAccessLoading(true)
    setShowDbAccess(true)
    try {
      setDbPermissions(await accessService.listDatabase(database.id))
    } catch (err) {
      notify('error', 'Accès', err.message)
      setShowDbAccess(false)
    } finally {
      setDbAccessLoading(false)
    }
  }

  const grantDbAccess = async () => {
    if (!database || !dbAccessEmail.trim()) return
    const rights = dbGrantLevel === 'MANAGE'
      ? { can_read: true, can_write: true, can_ddl: true, can_admin: true }
      : dbGrantLevel === 'EDIT'
        ? { can_read: true, can_write: true, can_ddl: true, can_admin: false }
        : { can_read: true, can_write: false, can_ddl: false, can_admin: false }
    try {
      await accessService.grantDatabase(database.id, { email: dbAccessEmail.trim(), ...rights })
      setDbPermissions(await accessService.listDatabase(database.id))
      setDbAccessEmail('')
      notify('success', 'Accès partagé', `${dbGrantLevel} accordé sur « ${database.name} »`)
    } catch (err) { notify('error', 'Partage impossible', err.message) }
  }

  const revokeDbAccess = async (permission) => {
    if (!database) return
    try {
      await accessService.revokeDatabase(database.id, permission.user_id)
      setDbPermissions(prev => prev.filter(item => item.user_id !== permission.user_id))
    } catch (err) { notify('error', 'Retrait impossible', err.message) }
  }

  const openColumnModal = useCallback(async (col) => {
    if (!currentTable) { notify('error', 'Aucune table', ''); return }
    if (!requireUnlocked(currentTable)) return
    setFkTableId('')
    setFkColumnName('')
    setFkColumnOptions([])
    if (col) {
      // Édition : préremplir le formulaire et pré-sélectionner la FK (format « table.colonne »)
      const dot = (col.references || '').indexOf('.')
      const refTable = dot > 0 ? col.references.slice(0, dot) : ''
      const refColumn = dot > 0 ? col.references.slice(dot + 1) : ''
      setColForm({
        name: col.name,
        type: col.type,
        length: col.length,
        default: col.default || '',
        nullable: col.nullable,
        primary_key: col.primary_key,
        foreign_key: col.foreign_key,
        references: col.references || '',
        unique: col.unique,
        auto_increment: col.auto_increment,
        index: col.index,
        on_delete: col.on_delete || 'NO ACTION',
        on_update: col.on_update || 'NO ACTION'
      })
      setShowEditCol(col)
      if (refTable) {
        const target = tables.find(t => t.name === refTable)
        if (target) {
          setFkTableId(String(target.id))
          setFkColumnName(refColumn || '')
          try {
            const cols = await columnService.list(target.id, false)
            setFkColumnOptions(cols)
          } catch { setFkColumnOptions([]) }
        }
      }
    } else {
      setColForm(emptyColumnForm)
      setShowEditCol('new')
    }
  }, [currentTable, notify, requireUnlocked, tables])

  const handleFkTableChange = async (tableId) => {
    setFkTableId(tableId)
    setFkColumnName('')
    if (!tableId) { setFkColumnOptions([]); return }
    try {
      const cols = await columnService.list(Number(tableId), false)
      setFkColumnOptions(cols)
    } catch { setFkColumnOptions([]) }
  }

  const handleCreateColumn = async () => {
    if (!currentTable) return
    if (!requireUnlocked(currentTable)) return
    if (!colForm.name.trim()) { notify('error', 'Nom requis', ''); return }
    if (colForm.foreign_key && (!fkTableId || !fkColumnName)) { notify('error', 'Référence incomplète', 'Sélectionnez la table et la colonne référencées'); return }
    try {
      const refTable = tables.find(t => String(t.id) === String(fkTableId))
      const references = colForm.foreign_key && refTable && fkColumnName ? `${refTable.name}.${fkColumnName}` : null
      const payload = {
        name: colForm.name.trim(),
        type: colForm.type,
        length: colForm.length || '-',
        nullable: colForm.nullable,
        primary_key: colForm.primary_key,
        foreign_key: colForm.foreign_key,
        references,
        unique: colForm.unique,
        auto_increment: colForm.auto_increment,
        index: colForm.index,
        on_delete: colForm.on_delete,
        on_update: colForm.on_update,
        default: colForm.default === '' ? null : colForm.default,
        table_id: currentTable.id
      }
      if (showEditCol && typeof showEditCol === 'object' && showEditCol.id) {
        const upd = await columnService.update(showEditCol.id, payload, documentVersion)
        setColumns(prev => prev.map(c => c.id === upd.id ? upd : c))
        notify('success', 'Colonne mise à jour', '')
      } else {
        const created = await columnService.create(payload, documentVersion)
        setColumns(prev => [...prev, created])
        notify('success', 'Colonne créée', '')
      }
      setShowEditCol(null)
      setColForm(emptyColumnForm)
      await fetchDatabase()
      await fetchTableXml(currentTable)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      if (!handleConflict(err)) notify('error', 'Erreur colonne', err.message)
    }
  }

  const handleDeleteColumn = async (col) => {
    if (!currentTable) return
    if (!requireUnlocked(currentTable)) return
    if (!window.confirm(`Supprimer colonne « ${col.name} » ?`)) return
    try {
      await columnService.delete(col.id, documentVersion)
      setColumns(prev => prev.filter(c => c.id !== col.id))
      notify('success', 'Colonne supprimée', '')
      await fetchDatabase()
      await fetchTableXml(currentTable)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      if (!handleConflict(err)) notify('error', 'Erreur', err.message)
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
    if (!requireUnlocked(currentTable)) return
    if (xmlError) {
      notify('error', 'XML invalide', xmlError)
      return
    }
    setSyncing(true)
    try {
      const result = await tableService.syncXml(currentTable.id, xmlCode, documentVersion)
      if (result.sql) setSqlCode(result.sql)
      if (result.xml) setXmlCode(result.xml)
      await fetchTables()
      await fetchColumns(currentTable.id)
      await fetchRows(currentTable.id)
      await fetchDatabase()
      if (result.table) setCurrentTable(previous => ({ ...previous, ...result.table, access: previous?.access }))
      if (result.document_version != null) setDocumentVersion(result.document_version)
      notify('success', 'Modifications appliquées', `Version ${result.document_version} synchronisée dans le stockage XML.`)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      if (!handleConflict(err)) notify('error', 'Erreur sync', err.message)
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
      const result = await syncService.syncDatabase(dbId, text, documentVersion)
      if (result.document_version != null) setDocumentVersion(result.document_version)
      await fetchTables()
      await fetchDatabase()
      setShowImport(false)
      notify('success', 'Import réussi', 'Base synchronisée')
    } catch (err) {
      if (!handleConflict(err)) notify('error', 'Erreur import', err.message)
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

  // Row handling
  const openNewRow = () => {
    if (!currentTable) return
    if (!requireUnlocked(currentTable)) return
    const init = {}
    columns.forEach(c => { init[c.name] = '' })
    setRowForm(init)
    setShowRowModal('new')
  }

  const openEditRow = (row) => {
    if (!requireUnlocked(currentTable)) return
    setRowForm({ ...row.data })
    setShowRowModal(row)
  }

  const handleSaveRow = async () => {
    if (!currentTable) return
    try {
      const payload = Object.fromEntries(Object.entries(rowForm).filter(([name, value]) => {
        const column = columns.find(item => item.name === name)
        return value !== '' || (!column?.auto_increment && column?.default == null)
      }))
      if (showRowModal === 'new') {
        await rowService.create(currentTable.id, payload, documentVersion)
        notify('success', 'Ligne ajoutée', '')
      } else {
        await rowService.update(currentTable.id, showRowModal.id, payload, documentVersion)
        notify('success', 'Ligne modifiée', '')
      }
      setShowRowModal(null)
      await fetchDatabase()
      await fetchRows(currentTable.id)
      await fetchTableXml(currentTable)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      if (!handleConflict(err)) notify('error', 'Erreur ligne', err.message)
    }
  }

  const handleDeleteRow = async (row) => {
    if (!currentTable) return
    if (!requireUnlocked(currentTable)) return
    if (!window.confirm(`Supprimer ligne #${row.id} ?`)) return
    try {
      await rowService.delete(currentTable.id, row.id, documentVersion)
      setRows(prev => prev.filter(r => r.id !== row.id))
      notify('success', 'Ligne supprimée', '')
      await fetchDatabase()
      await fetchTableXml(currentTable)
    } catch (err) {
      if (err.status === 403) setShowUnlock(currentTable)
      if (!handleConflict(err)) notify('error', 'Erreur', err.message)
    }
  }

  const databaseAccess = database?.access || {}
  const tableAccess = currentTable?.access || databaseAccess
  const canWriteRows = Boolean(tableAccess.can_write)
  const canEditStructure = Boolean(tableAccess.can_ddl)
  const canManage = Boolean(tableAccess.can_admin)
  const canEditXml = canManage && (!currentTable?.is_protected || isUnlocked(currentTable?.id))
  const outgoingRelations = columns.filter(column => column.foreign_key && column.references)
  const incomingRelations = Object.entries(relationColumns).flatMap(([tableName, tableColumns]) =>
    tableColumns.filter(column => column.references?.startsWith(`${currentTable?.name}.`)).map(column => ({ tableName, column })),
  )

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
          Bases de données
        </a>
        <div className="ws-crumb">/ <b>{database?.name || dbName}</b> / <span>{currentTable?.name || '—'}</span></div>
        <span className={`badge ${database?.status === 'ARCHIVED' ? 'badge-gray' : 'badge-green'}`}><span className="badge-dot" style={{ background: database?.status === 'ARCHIVED' ? '#A0AEC0' : '#22C55E' }}></span>{database?.status || 'ACTIF'}</span>
        <div className="ws-titlebar-right">
          <span className="badge badge-blue" title={`Version XML ${documentVersion || '—'} · accès ${databaseAccess.level || 'VIEW'}`}><span className="badge-dot" style={{ background: '#3B82F6' }}></span>XML synchronisé</span>
          {canManage && <button className="btn btn-sm" onClick={openDbAccess} title="Partager la base avec d'autres utilisateurs">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            Partage
          </button>}
          {canManage && <button className="btn btn-sm" onClick={handleExportProject} title="Exporter projet complet avec données et protections">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
            Export complet
          </button>}
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
              const unlocked = !t.is_protected || isUnlocked(t.id)
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
            {databaseAccess.can_ddl && <button className="btn btn-sm" onClick={() => setShowNewTable(true)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14"/></svg>
              Nouvelle table
            </button>}
            {databaseAccess.can_ddl && <button className="btn btn-sm" onClick={() => setShowImport(true)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
              Importer XML
            </button>}
            <button className="btn btn-sm" onClick={async () => { try { await exportService.exportSql(dbId, { download: true, name: database?.name }); notify('success', 'Export réussi', 'Le script SQL a été généré avec succès.') } catch (err) { notify('error', 'Erreur', err.message) } }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v14"/></svg>
              Exporter SQL
            </button>
          </div>
        </aside>

        <main className="ws-main">
          <div className="db-overview" style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', padding: '10px 16px', borderBottom: '1px solid var(--border-soft)', background: 'var(--bg-elevated)', fontSize: '12px', color: 'var(--text-secondary)' }}>
            <span className={`badge ${database?.scope === 'COMMON' ? 'badge-warn' : 'badge-blue'}`}>{database?.scope === 'COMMON' ? 'Base commune' : 'Base personnelle'}</span>
            <span>Propriétaire : <b style={{ color: 'var(--text)' }}>{database?.owner_name || database?.creator_name || '—'}</b></span>
            <span>Accès : <b style={{ color: 'var(--text)' }}>{databaseAccess.level || '—'}</b></span>
            <span>Version XML : <b style={{ color: 'var(--text)', fontFamily: 'var(--font-mono)' }}>{documentVersion ?? '—'}</b></span>
            {database?.description ? <span className="dim" style={{ color: 'var(--text-tertiary)' }}>{database.description}</span> : <span className="dim" style={{ color: 'var(--text-tertiary)' }}>Aucune description</span>}
          </div>
          <div className="ws-main-head">
            <div className="ws-main-head-left">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              <div>
                <h2>{currentTable?.name || 'Aucune table'}{currentTable?.is_protected ? <span style={{ marginLeft: '8px', color: 'var(--warn)', display: 'inline-flex' }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></span> : ''}</h2>
                <div className="sub">{currentTable ? `${columns.length} colonnes · ${rowsTotal} lignes · clé primaire : ${columns.find(c => c.primary_key)?.name || '—'} · statut : ${currentTable.status === 'ARCHIVED' ? 'archivée' : 'active'}` : 'Sélectionnez une table'}</div>
              </div>
            </div>
            <div className="ws-main-actions">
              <button className="btn btn-sm" disabled={!canEditStructure} onClick={() => openColumnModal(null)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Ajouter une colonne
              </button>
              <button className="btn btn-sm" onClick={handleArchiveToggle} disabled={!canEditStructure}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8"/><path d="M10 12h4"/></svg>
                <span>{currentTable?.status === 'ARCHIVED' ? 'Restaurer' : 'Archiver'}</span>
              </button>
              <button className="btn btn-sm btn-danger" disabled={!canEditStructure} onClick={() => {
                if (!currentTable) return
                if (!requireUnlocked(currentTable)) return
                setShowDeleteTable(true)
              }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
                Supprimer la table
              </button>
              {currentTable && canEditStructure && !currentTable.is_protected && (
                <button className="btn btn-sm" onClick={() => setShowProtect(true)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  Protéger
                </button>
              )}
              {currentTable && canEditStructure && currentTable.is_protected && isUnlocked(currentTable.id) && (
                <button className="btn btn-sm" onClick={handleUnprotect}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.5-2"/></svg>
                  Ôter la protection
                </button>
              )}
              {currentTable && canManage && (
                <button className="btn btn-sm" onClick={openTableAccess}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                  Partage de la table
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
              <button className={`tab-btn ${tab === 'relations' ? 'active' : ''}`} onClick={() => setTab('relations')}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l2-2a5 5 0 0 0-7.07-7.07l-1.14 1.14"/><path d="M14 11a5 5 0 0 0-7.54-.54l-2 2a5 5 0 0 0 7.07 7.07l1.14-1.14"/></svg>
                Relations
              </button>
              <button className={`tab-btn ${tab === 'advanced' ? 'active' : ''}`} onClick={() => setTab('advanced')}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                Avancé
              </button>
            </div>
          </div>

          <div className={`tab-panel ${tab === 'structure' ? 'active' : ''}`}>
            <div className="table-wrap">
              <table className="cols-table">
                <thead>
                  <tr>
                    <th>Nom</th><th>Type</th><th>Longueur</th><th>Nullable</th><th>PK</th><th>FK</th><th>Unique</th><th>Auto Inc.</th><th>Index</th><th>État</th><th>Modifié par</th><th style={{ textAlign: 'right' }}>Actions</th>
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
                      <td>{c.foreign_key ? <span className="fk-tag" title={c.references || ''}>FK</span> : boolChip(false)}</td>
                      <td>{boolChip(c.unique)}</td>
                      <td>{boolChip(c.auto_increment)}</td>
                      <td>{boolChip(c.index)}</td>
                      <td><span className={`badge ${c.status === 'ARCHIVED' ? 'badge-gray' : 'badge-green'}`} style={{ padding: '2px 8px' }}>{c.status || 'ACTIVE'}</span></td>
                      <td style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{c.last_modified_by || '—'}</td>
                      <td>
                        <div className="row-actions">
                          <button className="icon-btn sm" title="Modifier" disabled={!canEditStructure} onClick={() => openColumnModal(c)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                          </button>
                          <button className="icon-btn sm danger" title="Supprimer" disabled={!canEditStructure} onClick={() => handleDeleteColumn(c)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {columns.length === 0 && (
                    <tr><td colSpan={12}><div className="empty-state" style={{ padding: '30px' }}><div className="es-title">Aucune colonne</div><div className="es-desc">Ajoutez votre première colonne.</div></div></td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className={`tab-panel ${tab === 'data' ? 'active' : ''}`}>
            <div className="data-tab-wrap">
              {columns.length === 0 ? (
                <div className="empty-state" style={{ padding: '40px' }}>
                  <div className="es-title">Aucune colonne définie</div>
                  <div className="es-desc">Créez d'abord des colonnes dans l'onglet Structure pour pouvoir gérer les données.</div>
                </div>
              ) : (
                <>
                  <div className="data-toolbar" style={{ borderBottom: '1px solid var(--border)', paddingBottom: 14 }}>
                    <input className="form-input" placeholder="Rechercher dans les lignes..." value={rowSearch} onChange={e => { setRowSearch(e.target.value); setPage(1) }} />
                    <select className="form-input" value={rowSort} onChange={e => { setRowSort(e.target.value); setPage(1) }}><option value="">Tri par défaut</option>{columns.map(col => <option key={col.id} value={col.name}>{col.name}</option>)}</select>
                    <button className="btn btn-sm" disabled={!rowSort} onClick={() => setRowOrder(order => order === 'ASC' ? 'DESC' : 'ASC')}>{rowOrder}</button>
                    <button className="btn btn-sm" onClick={() => fetchRows(currentTable.id)}>Actualiser</button>
                    {canWriteRows && <button className="btn btn-sm btn-primary" onClick={openNewRow}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><path d="M12 5v14M5 12h14"/></svg>Ajouter une ligne</button>}
                    <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-tertiary)' }}>{rowsTotal} ligne{rowsTotal > 1 ? 's' : ''}</span>
                  </div>
                  {rowsError && <div className="danger-box" style={{ margin: 12 }}>{rowsError}</div>}
                  {rowsLoading ? <div className="empty-state"><span className="mini-spinner"/><div className="es-title">Chargement des données...</div></div> : <table className="cols-table">
                  <thead>
                    <tr>
                      {columns.map(col => <th key={col.id}>{col.name}{col.primary_key && <span className="pk-tag" style={{ marginLeft: 4 }}>PK</span>}</th>)}
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(row => (
                      <tr key={row.id}>
                        {columns.map(col => (
                          <td key={col.id} style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                            {row.data[col.name] === null ? <span className="badge badge-gray">NULL</span> : row.data[col.name] !== undefined ? String(row.data[col.name]) : <span style={{ color: 'var(--text-tertiary)' }}>—</span>}
                          </td>
                        ))}
                        <td>
                          <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                            <button className="icon-btn sm" title="Modifier" disabled={!canWriteRows} onClick={() => openEditRow(row)}>
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                            </button>
                            <button className="icon-btn sm danger" title="Supprimer" disabled={!canWriteRows} onClick={() => handleDeleteRow(row)}>
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {rows.length === 0 && (
                      <tr><td colSpan={columns.length + 1}><div className="empty-state" style={{ padding: '30px' }}><div className="es-title">Aucune donnée</div><div className="es-desc">Ajoutez votre première ligne. Les données sont stockées dans XMLForge et exportées dans le XML.</div></div></td></tr>
                    )}
                  </tbody>
                </table>}
                  <div className="filters-bar" style={{ padding: '10px 12px' }}>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Page {page} · {rowsTotal} ligne(s)</span>
                    <button className="btn btn-sm" disabled={page <= 1 || rowsLoading} onClick={() => setPage(value => Math.max(1, value - 1))}>Précédent</button>
                    <button className="btn btn-sm" disabled={page * pageSize >= rowsTotal || rowsLoading} onClick={() => setPage(value => value + 1)}>Suivant</button>
                  </div>
                </>
              )}
            </div>
          </div>

          <div className={`tab-panel ${tab === 'relations' ? 'active' : ''}`}>
            <div className="panel-scroll" id="relations-wrap">
              {relationsLoading ? <div className="empty-state"><span className="mini-spinner"/><div className="es-title">Chargement des relations...</div></div> : <>
                <div className="rel-section-title">Table courante</div>
                <div className="rel-current-card"><div><div className="rel-current-name">{currentTable?.name || '—'}</div><div className="rel-current-sub">Clé primaire : {columns.find(column => column.primary_key)?.name || '—'} · {columns.length} colonne(s)</div></div></div>
                <div className="rel-section-title">Relations sortantes</div>
                {outgoingRelations.length === 0 ? <div className="empty-state" style={{ padding: 20 }}><div className="es-desc">Aucune clé étrangère sortante.</div></div> : <div className="rel-list">{outgoingRelations.map(column => <div className="rel-row" key={column.id}><span className="fk-tag">FK</span><span className="rel-row-col">{column.name}</span><span className="rel-row-arrow">→</span><span className="rel-row-target">{column.references}</span></div>)}</div>}
                <div className="rel-section-title">Relations entrantes</div>
                {incomingRelations.length === 0 ? <div className="empty-state" style={{ padding: 20 }}><div className="es-desc">Aucune autre table ne référence cette table.</div></div> : <div className="rel-list">{incomingRelations.map(({ tableName, column }) => <div className="rel-row" key={`${tableName}-${column.id}`}><span className="pk-tag">FK</span><span className="rel-row-col">{tableName}.{column.name}</span><span className="rel-row-arrow">→</span><span className="rel-row-target">{column.references}</span></div>)}</div>}
              </>}
            </div>
          </div>

          <div className={`tab-panel ${tab === 'advanced' ? 'active' : ''}`}>
            <div className="panel-scroll">
              <div className="rel-section-title">Protection de la table</div>
              <div className="api-card">
                <div className="api-card-top">
                  <div className="api-card-top-left">
                    <div className="api-card-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="19" height="19">{currentTable?.is_protected ? <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></> : <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.5-2"/></>}</svg>
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '14.5px' }}>« {currentTable?.name || '—'} » est {currentTable?.is_protected ? 'protégée' : 'non protégée'}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {currentTable?.is_protected
                          ? 'Un code de protection est requis pour la modifier. Le déverrouillage via ce code n’est valable que pour votre session.'
                          : 'Aucune restriction de modification n’est active sur cette table.'}
                      </div>
                    </div>
                  </div>
                  <span className={`badge ${currentTable?.is_protected ? 'badge-warn' : 'badge-gray'}`}>{currentTable?.is_protected ? 'PROTÉGÉE' : 'LIBRE'}</span>
                </div>
                {currentTable?.is_protected ? (
                  <div className="modal-footer" style={{ padding: '16px 0 0', borderTop: 'none' }}>
                    {isUnlocked(currentTable?.id) && canEditStructure && (
                      <button className="btn btn-sm btn-danger" onClick={handleUnprotect}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.5-2"/></svg>
                        Retirer la protection définitivement
                      </button>
                    )}
                    {!isUnlocked(currentTable?.id) && (
                      <button className="btn btn-sm btn-primary" onClick={() => setShowUnlock(currentTable)}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                        Déverrouiller pour cette session
                      </button>
                    )}
                  </div>
                ) : (
                  canEditStructure && (
                    <div className="modal-footer" style={{ padding: '16px 0 0', borderTop: 'none' }}>
                      <button className="btn btn-sm" onClick={() => setShowProtect(true)}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                        Protéger la table
                      </button>
                    </div>
                  )
                )}
              </div>

              <div className="rel-section-title" style={{ marginTop: 22 }}>Stockage</div>
              <div className="api-card">
                <p className="desc" style={{ margin: 0 }}>
                  Base stockée et synchronisée <b style={{ color: '#fff' }}>exclusivement en XML</b> (moteur XML natif, aucune projection relationnelle).
                </p>
              </div>

              <div className="rel-section-title" style={{ marginTop: 22 }}>Synchronisation & conflits</div>
              <div className="api-card">
                <p className="desc" style={{ margin: '0 0 12px' }}>
                  Chaque modification transmet la <b style={{ color: '#fff' }}>version attendue</b> (expected_version).
                  Si la base a été modifiée entre-temps, le serveur répond <b style={{ color: '#fff' }}>409 Conflict</b> :
                  l'interface n'est alors plus à jour et doit être rafraîchie avant de réessayer.
                </p>
                <div className="modal-footer" style={{ padding: 0, borderTop: 'none' }}>
                  <span className="badge badge-blue" style={{ marginRight: 'auto' }}>Version XML courante : {documentVersion ?? '—'}</span>
                  <button className="btn btn-sm" onClick={async () => { await fetchDatabase(); await fetchTables(); if (currentTable?.id) { await fetchColumns(currentTable.id); await fetchRows(currentTable.id); await fetchTableXml(currentTable) } notify('info', 'Vue actualisée', 'La table a été rechargée avec les dernières données.') }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
                    Rafraîchir
                  </button>
                </div>
              </div>

              <div className="rel-section-title" style={{ marginTop: 22 }}>Fonctionnalités avancées (XML / REST)</div>
              <div className="info-box" style={{ marginBottom: 0 }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                <span>Le backend prend en charge des cas non couverts ici en un clic : clés primaires composites (plusieurs colonnes), clés étrangères déclarées au niveau table, et actions d'index avancées. Ces cas restent accessibles via l'éditeur XML (panneau de droite) ou l'API REST.</span>
              </div>
            </div>
          </div>
        </main>

        <aside className="ws-right">
          <div className={`code-pane ${fullscreenPane === 'xml' ? 'pane-fullscreen' : ''}`} id="pane-xml">
            <div className="code-pane-head">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
              XML Source
              <span className="lang-badge">XML</span>
              {xmlError && <span className="badge badge-red" title={xmlError}>Erreur XML</span>}
              <div className="code-pane-head-actions">
                <button className="icon-btn sm" title="Copier" onClick={() => handleCopy(xmlCode)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
                <button className="icon-btn sm" title="Télécharger" onClick={() => handleDownload(xmlCode, `${currentTable?.name || 'table'}.xml`)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg></button>
                <button className="icon-btn sm" title="Plein écran" onClick={() => setFullscreenPane(value => value === 'xml' ? null : 'xml')}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg></button>
              </div>
            </div>
            <div className="code-pane-body" style={{ padding: 0, display: 'flex', flexDirection: 'column', minHeight: '240px' }}>
              {xmlLoading ? (
                <div style={{ padding: '20px', color: 'var(--text-tertiary)', fontSize: '12px' }}>Chargement XML...</div>
              ) : (
                <MonacoEditor value={xmlCode} onChange={setXmlCode} language="xml" readOnly={!canEditXml} />
              )}
            </div>
            {xmlError && <div style={{ padding: '6px 12px', fontSize: '11px', color: '#FF8787', background: 'var(--danger-soft)', borderTop: '1px solid #EF444440' }}>⚠ {xmlError.slice(0, 200)}</div>}
          </div>

          <div className="apply-row">
            <button className="btn btn-sm btn-block" onClick={handleConvertXmlToSql} disabled={converting || !xmlCode}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M19 12l-7 7-7-7"/></svg>
              {converting ? 'Conversion...' : 'Convertir XML → SQL'}
            </button>
            <button className="btn btn-sm btn-primary btn-block" onClick={handleApplyChanges} disabled={syncing || !canEditXml || Boolean(xmlError)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
              {syncing ? 'Synchronisation...' : 'Appliquer les modifications'}
            </button>
            <div className="apply-hint">POST /tables/{'{id}'}/sync-xml · personnel par utilisateur</div>
          </div>

          <div className={`code-pane ${fullscreenPane === 'sql' ? 'pane-fullscreen' : ''}`} id="pane-sql">
            <div className="code-pane-head">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
              SQL généré
              <span className="lang-badge">SQL</span>
              <div className="code-pane-head-actions">
                <button className="icon-btn sm" title="↑ SQL → XML" onClick={handleConvertSqlToXml}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>
                <button className="icon-btn sm" title="Copier" onClick={() => handleCopy(sqlCode)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
                <button className="icon-btn sm" title="Télécharger" onClick={() => handleDownload(sqlCode, `${currentTable?.name || 'table'}.sql`)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg></button>
                <button className="icon-btn sm" title="Plein écran" onClick={() => setFullscreenPane(value => value === 'sql' ? null : 'sql')}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg></button>
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
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>Importer un fichier XML</h3>
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

      <div className={`modal-overlay ${showNewTable ? 'open' : ''}`} onClick={() => setShowNewTable(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>Nouvelle table</h3>
            <button className="icon-btn" onClick={() => setShowNewTable(false)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <div className="field-block"><label className="form-label">Nom de la table</label><input className="form-input" type="text" placeholder="ex. commande" value={newTableForm.name} onChange={e => setNewTableForm(f => ({ ...f, name: e.target.value }))} /></div>
            <div className="check-row"><label className="switch"><input type="checkbox" checked={newTableForm.withId} onChange={e => setNewTableForm(f => ({ ...f, withId: e.target.checked }))} /><span className="track"></span></label><label>Ajouter automatiquement une clé primaire "id"</label></div>
            <div className="check-row"><label className="switch"><input type="checkbox" checked={newTableForm.protected} onChange={e => setNewTableForm(f => ({ ...f, protected: e.target.checked }))} /><span className="track"></span></label><label>Table protégée</label></div>
            {newTableForm.protected && (
              <div className="field-block" style={{ marginTop: '10px' }}>
                <label className="form-label">Code de protection</label>
                <input className="form-input" type="text" placeholder="ex. XML-9F4A-2C1B" style={{ fontFamily: 'var(--font-mono)' }} value={newTableForm.key} onChange={e => setNewTableForm(f => ({ ...f, key: e.target.value }))} />
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowNewTable(false)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleCreateTable}>Créer la table</button>
          </div>
        </div>
      </div>

      <div className={`modal-overlay ${showEditCol ? 'open' : ''}`} onClick={() => setShowEditCol(null)}>
        <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>Ajouter / Modifier une colonne</h3>
            <button className="icon-btn" onClick={() => setShowEditCol(null)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <div className="grid-2">
              <div className="field-block"><label className="form-label">Nom</label><input className="form-input" value={colForm.name} onChange={e => setColForm(f => ({ ...f, name: e.target.value }))} /></div>
              <div className="field-block"><label className="form-label">Type</label><select className="form-input" value={colForm.type} onChange={e => setColForm(f => ({ ...f, type: e.target.value }))}><option>VARCHAR</option><option>CHAR</option><option>TEXT</option><option>CLOB</option><option>INT</option><option>INTEGER</option><option>BIGINT</option><option>SMALLINT</option><option>TINYINT</option><option>DECIMAL</option><option>NUMERIC</option><option>REAL</option><option>FLOAT</option><option>DOUBLE</option><option>BOOLEAN</option><option>BOOL</option><option>DATE</option><option>DATETIME</option><option>TIMESTAMP</option><option>TIME</option><option>BLOB</option><option>JSON</option></select></div>
            </div>
            <div className="grid-2">
              <div className="field-block"><label className="form-label">Longueur</label><input className="form-input" value={colForm.length} onChange={e => setColForm(f => ({ ...f, length: e.target.value }))} /></div>
              <div className="field-block"><label className="form-label">Valeur par défaut</label><input className="form-input" value={colForm.default} onChange={e => setColForm(f => ({ ...f, default: e.target.value }))} placeholder="laisser vide = aucun défaut" /></div>
            </div>
            <div className="grid-2" style={{ marginTop: '4px' }}>
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.nullable} onChange={e => setColForm(f => ({ ...f, nullable: e.target.checked }))} /><span className="track"></span></label><label>Nullable</label></div>
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.unique} onChange={e => setColForm(f => ({ ...f, unique: e.target.checked }))} /><span className="track"></span></label><label>Unique</label></div>
            </div>
            <div className="grid-2">
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.primary_key} onChange={e => setColForm(f => ({ ...f, primary_key: e.target.checked }))} /><span className="track"></span></label><label>Clé primaire</label></div>
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.auto_increment} onChange={e => setColForm(f => ({ ...f, auto_increment: e.target.checked }))} /><span className="track"></span></label><label>Auto-incrément</label></div>
            </div>
            <div className="grid-2">
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.index} onChange={e => setColForm(f => ({ ...f, index: e.target.checked }))} /><span className="track"></span></label><label>Index</label></div>
              <div className="check-row"><label className="switch"><input type="checkbox" checked={colForm.foreign_key} onChange={e => setColForm(f => ({ ...f, foreign_key: e.target.checked }))} /><span className="track"></span></label><label>Clé étrangère</label></div>
            </div>
            {colForm.foreign_key && (
              <div className="fk-fields-block">
                <div className="grid-2">
                  <div className="field-block">
                    <label className="form-label">Table référencée</label>
                    <select className="form-input" value={fkTableId} onChange={e => handleFkTableChange(e.target.value)}>
                      <option value="">— Sélectionner —</option>
                      {tables.filter(t => t.id !== currentTable?.id).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  </div>
                  <div className="field-block">
                    <label className="form-label">Colonne référencée</label>
                    <select className="form-input" value={fkColumnName} onChange={e => setFkColumnName(e.target.value)} disabled={!fkTableId}>
                      <option value="">— Sélectionner —</option>
                      {fkColumnOptions.map(c => <option key={c.id} value={c.name}>{c.name}</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid-2">
                  <div className="field-block">
                    <label className="form-label">ON DELETE</label>
                    <select className="form-input" value={colForm.on_delete} onChange={e => setColForm(f => ({ ...f, on_delete: e.target.value }))}><option>RESTRICT</option><option>CASCADE</option><option>SET NULL</option><option>NO ACTION</option></select>
                  </div>
                  <div className="field-block">
                    <label className="form-label">ON UPDATE</label>
                    <select className="form-input" value={colForm.on_update} onChange={e => setColForm(f => ({ ...f, on_update: e.target.value }))}><option>RESTRICT</option><option>CASCADE</option><option>SET NULL</option><option>NO ACTION</option></select>
                  </div>
                </div>
              </div>
            )}
            <div className="info-box" style={{ marginTop: 2, marginBottom: 0 }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
              <span>Ce formulaire couvre les cas simples (PK simple, FK simple, index, actions référentielles). Pour une <b style={{ color: '#fff' }}>clé primaire composite</b> (plusieurs colonnes) ou une <b style={{ color: '#fff' }}>clé étrangère complexe</b>, utilisez l'éditeur XML ou l'API REST — cochez « Clé primaire » sur chacune des colonnes concernées pour composer une PK composite.</span>
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

      {/* Database access modal */}
      <div className={`modal-overlay ${showDbAccess ? 'open' : ''}`} onClick={() => setShowDbAccess(false)}>
        <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Accès à {database?.name}</h3><button className="icon-btn" onClick={() => setShowDbAccess(false)}>✕</button></div>
          <div className="modal-body">
            <p className="desc">Partagez cette base par email. VIEW = lecture, EDIT = écritures + structure, MANAGE = administration des accès. Les bases COMMON ne deviennent visibles qu'après un partage explicite.</p>
            <div className="grid-2"><input className="form-input" type="email" placeholder="utilisateur@exemple.com" value={dbAccessEmail} onChange={e => setDbAccessEmail(e.target.value)} /><select className="form-input" value={dbGrantLevel} onChange={e => setDbGrantLevel(e.target.value)}><option>VIEW</option><option>EDIT</option><option>MANAGE</option></select></div>
            <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={grantDbAccess} disabled={!dbAccessEmail.trim()}>Accorder</button>
            <div style={{ marginTop: 18 }}>
              {dbAccessLoading ? <div className="skeleton" style={{ height: 42 }} /> : dbPermissions.length === 0 ? <div className="empty-state" style={{ padding: 20 }}><div className="es-title">Aucun partage</div></div> : dbPermissions.map(permission => (
                <div className="rel-row" key={permission.id}><span className="rel-row-col">{permission.user_email || `User #${permission.user_id}`}</span><span className="badge badge-blue">{permission.can_admin ? 'MANAGE' : permission.can_write || permission.can_ddl ? 'EDIT' : 'VIEW'}</span><button className="icon-btn sm danger" style={{ marginLeft: 'auto' }} onClick={() => revokeDbAccess(permission)}>✕</button></div>
              ))}
            </div>
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowDbAccess(false)}>Fermer</button></div>
        </div>
      </div>

      {/* Table access modal */}
      <div className={`modal-overlay ${showTableAccess ? 'open' : ''}`} onClick={() => setShowTableAccess(false)}>
        <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Partage de la table {currentTable?.name}</h3><button className="icon-btn" onClick={() => setShowTableAccess(false)}>✕</button></div>
          <div className="modal-body">
            <p className="desc">Les droits de table sont <b>additifs</b> par rapport à ceux de la base : ils ne peuvent pas retirer un droit existant. Un partage de table seul ne rend pas la base sélectionnable dans le Dashboard ; accordez au moins la lecture sur la base si nécessaire.</p>
            <div className="grid-2"><input className="form-input" type="email" placeholder="utilisateur@exemple.com" value={tableAccessEmail} onChange={e => setTableAccessEmail(e.target.value)} /><select className="form-input" value={tableGrantLevel} onChange={e => setTableGrantLevel(e.target.value)}><option>VIEW</option><option>EDIT</option><option>MANAGE</option></select></div>
            <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={grantTableAccess} disabled={!tableAccessEmail.trim()}>Accorder</button>
            <div style={{ marginTop: 18 }}>
              {tableAccessLoading ? <div className="skeleton" style={{ height: 42 }} /> : tablePermissions.length === 0 ? <div className="empty-state" style={{ padding: 20 }}><div className="es-title">Aucun partage</div><div className="es-desc">Cette table n'a pas de permission spécifique.</div></div> : tablePermissions.map(permission => (
                <div className="rel-row" key={permission.id}><span className="rel-row-col">{permission.user_email || `User #${permission.user_id}`}</span><span className="badge badge-blue">{permission.can_admin ? 'MANAGE' : permission.can_write || permission.can_ddl ? 'EDIT' : 'VIEW'}</span><button className="icon-btn sm danger" style={{ marginLeft: 'auto' }} onClick={() => revokeTableAccess(permission)}>✕</button></div>
              ))}
            </div>
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowTableAccess(false)}>Fermer</button></div>
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
                    <div style={{ display: 'flex', gap: 8 }}><input className="form-input" disabled={rowForm[col.name] === null} value={rowForm[col.name] ?? ''} onChange={e => setRowForm(f => ({ ...f, [col.name]: e.target.value }))} placeholder={col.default || ''} />{col.nullable && <button className={`btn btn-sm ${rowForm[col.name] === null ? 'btn-primary' : ''}`} onClick={() => setRowForm(f => ({ ...f, [col.name]: f[col.name] === null ? '' : null }))}>NULL</button>}</div>
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

      <ConflictDialog open={conflict} onClose={() => setConflict(false)} onReload={async () => {
        setConflict(false)
        await fetchDatabase()
        await fetchTables()
        if (currentTable?.id) {
          await fetchColumns(currentTable.id)
          await fetchRows(currentTable.id)
          await fetchTableXml(currentTable)
        }
      }} />
    </div>
  )
}
