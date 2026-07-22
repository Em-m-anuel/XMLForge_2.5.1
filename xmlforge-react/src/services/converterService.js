import apiClient from './api'

export const converterService = {
  xmlToSql: async (xml, databaseName) => {
    const res = await apiClient.post('/convert/xml-to-sql', { xml, database_name: databaseName })
    return res.data // {sql}
  },

  sqlToXml: async (sql, databaseName) => {
    const res = await apiClient.post('/convert/sql-to-xml', { sql, database_name: databaseName })
    return res.data // {xml}
  },
}
