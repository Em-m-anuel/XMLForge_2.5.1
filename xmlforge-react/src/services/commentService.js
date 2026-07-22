import { databaseService } from './databaseService'
import { tableService } from './tableService'
import { columnService } from './columnService'

export const commentService = {
  getDatabaseComment: (id) => databaseService.getComment(id),
  updateDatabaseComment: (id, comment) => databaseService.updateComment(id, comment),

  getTableComment: (id) => tableService.getComment(id),
  updateTableComment: (id, comment, key) => tableService.updateComment(id, comment, key),

  getColumnComment: (id) => columnService.getComment(id),
  updateColumnComment: (id, comment, key) => columnService.updateComment(id, comment, key),
}
