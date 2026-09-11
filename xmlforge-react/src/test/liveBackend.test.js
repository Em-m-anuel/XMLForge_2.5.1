import { describe, expect, it } from 'vitest'
import { authService } from '../services/authService'
import { databaseService } from '../services/databaseService'
import { tableService } from '../services/tableService'
import { columnService } from '../services/columnService'
import { rowService } from '../services/rowService'
import { exportService } from '../services/exportService'
import { importService } from '../services/importService'
import { accessService } from '../services/accessService'

const live = process.env.XMLFORGE_LIVE_E2E === '1'
const liveIt = live ? it : it.skip

describe('Frontend services ↔ backend Flask réel', () => {
  liveIt('effectue login, CRUD, XML, COMMON collectif et conflit expected_version', async () => {
    const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    const email = `frontend-${suffix}@example.com`
    await authService.register({ full_name: 'Frontend E2E', email, password: 'secret123' })
    await authService.login({ email, password: 'secret123' })

    let database
    let commonDb
    let importedCopy
    try {
      // Base PERSONAL : partage individuel explicite.
      database = await databaseService.create({ name: `frontend_${Date.now()}`, scope: 'PERSONAL' })
      expect(database.scope).toBe('PERSONAL')
      expect(database.access).toMatchObject({ level: 'MANAGE', can_admin: true })

      const guestEmail = `guest-${suffix}@example.com`
      await authService.register({ full_name: 'Shared Viewer', email: guestEmail, password: 'secret123' })
      await accessService.grantDatabase(database.id, { email: guestEmail, can_read: true, can_write: false, can_ddl: false, can_admin: false })
      await authService.login({ email: guestEmail, password: 'secret123' })
      const sharedView = (await databaseService.list()).find(item => item.id === database.id)
      expect(sharedView.access).toMatchObject({ level: 'VIEW', source: 'shared' })

      // Base COMMON : accès collectif automatique (aucun partage requis).
      await authService.login({ email, password: 'secret123' })
      commonDb = await databaseService.create({ name: `common_${Date.now()}`, scope: 'COMMON', common_permission: 'VIEW' })
      await authService.login({ email: guestEmail, password: 'secret123' })
      const commonView = (await databaseService.list()).find(item => item.id === commonDb.id)
      expect(commonView.access).toMatchObject({ level: 'VIEW', source: 'common' })

      // CRUD via les services frontend.
      await authService.login({ email, password: 'secret123' })
      const staleVersion = database.document_version
      const table = await tableService.create({ name: 'items', database_id: database.id }, staleVersion)
      database = await databaseService.get(database.id)
      await columnService.create({ name: 'id', type: 'INTEGER', primary_key: true, auto_increment: true, nullable: false, table_id: table.id }, database.document_version)
      database = await databaseService.get(database.id)
      await columnService.create({ name: 'name', type: 'VARCHAR', nullable: false, unique: true, table_id: table.id }, database.document_version)
      database = await databaseService.get(database.id)
      await rowService.create(table.id, { name: 'Nyx' }, database.document_version)

      const rows = await rowService.list(table.id, { limit: 25 })
      expect(rows.rows).toHaveLength(1)
      expect(rows.rows[0].data.name).toBe('Nyx')
      const exported = await exportService.exportXml(database.id)
      expect(exported.xml).toContain('<cell column="name">Nyx</cell>')
      importedCopy = await importService.importXmlRaw(exported.xml, `${database.name}_copy`)
      const importedRows = await databaseService.list()
      expect(importedRows.some(item => item.id === importedCopy.id)).toBe(true)

      await expect(rowService.create(table.id, { name: 'stale' }, staleVersion))
        .rejects.toMatchObject({ status: 409, isConflict: true })
    } finally {
      await authService.login({ email, password: 'secret123' })
      // RESTRICT : révoquer les grants avant suppression (base PERSONAL partagée).
      if (database?.id) {
        const guestEmail = `guest-${suffix}@example.com`
        const guests = await accessService.listDatabase(database.id)
        for (const perm of (guests || [])) {
          if (perm.user_email === guestEmail) await accessService.revokeDatabase(database.id, perm.user_id)
        }
      }
      if (importedCopy?.id) await databaseService.delete(importedCopy.id)
      if (commonDb?.id) await databaseService.delete(commonDb.id)
      if (database?.id) await databaseService.delete(database.id)
      await authService.logout()
    }
  }, 120000)
})
