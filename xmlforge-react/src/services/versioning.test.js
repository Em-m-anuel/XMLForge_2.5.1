import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./api', () => ({
  default: {
    post: vi.fn(), put: vi.fn(), delete: vi.fn(), get: vi.fn(),
  },
}))

import apiClient from './api'
import { tableService } from './tableService'
import { rowService } from './rowService'
import { syncService } from './syncService'

beforeEach(() => {
  apiClient.post.mockReset().mockResolvedValue({ data: {} })
  apiClient.put.mockReset().mockResolvedValue({ data: {} })
  apiClient.delete.mockReset().mockResolvedValue({ data: {} })
})

describe('propagation expected_version', () => {
  it('l’envoie pour sync XML de table', async () => {
    await syncService.syncTable(4, '<table/>', 12)
    expect(apiClient.post).toHaveBeenCalledWith('/tables/4/sync-xml', { xml: '<table/>', expected_version: 12 })
  })

  it('l’envoie pour créations structurelles et rows', async () => {
    await tableService.create({ name: 'orders', database_id: 2 }, 8)
    expect(apiClient.post).toHaveBeenCalledWith('/tables', expect.objectContaining({ expected_version: 8 }))
    await rowService.create(3, { name: 'Nyx' }, 9)
    expect(apiClient.post).toHaveBeenLastCalledWith('/tables/3/rows', { data: { name: 'Nyx' }, expected_version: 9 })
  })

  it('utilise If-Match pour DELETE', async () => {
    await rowService.delete(3, 7, 14)
    expect(apiClient.delete).toHaveBeenCalledWith('/tables/3/rows/7', { headers: { 'If-Match': '14' } })
  })
})
