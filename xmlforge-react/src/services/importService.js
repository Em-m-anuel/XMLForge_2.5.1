import apiClient from './api'

export const importService = {
  importXml: async (file, { databaseName, description } = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (databaseName) form.append('database_name', databaseName)
    if (description) form.append('description', description)
    const res = await apiClient.post('/import/xml', form)
    return res.data
  },

  importSql: async (file, { databaseName, description } = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (databaseName) form.append('database_name', databaseName)
    if (description) form.append('description', description)
    const res = await apiClient.post('/import/sql', form)
    return res.data
  },

  importXmlRaw: async (xml, databaseName) => {
    const res = await apiClient.post('/import/xml', { xml, database_name: databaseName })
    return res.data
  },

  importSqlRaw: async (sql, databaseName) => {
    const res = await apiClient.post('/import/sql', { sql, database_name: databaseName })
    return res.data
  },
}
