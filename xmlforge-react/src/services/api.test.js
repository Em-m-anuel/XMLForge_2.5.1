import { describe, expect, it, vi } from 'vitest'
import apiClient, { ApiError } from './api'

function token(exp = Math.floor(Date.now() / 1000) + 3600) {
  return `header.${btoa(JSON.stringify({ exp }))}.signature`
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('apiClient centralisé', () => {
  it('ajoute le JWT et utilise le préfixe /api', async () => {
    localStorage.setItem('xmlforge_token', token())
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ success: true, data: [{ id: 1 }] }))
    vi.stubGlobal('fetch', fetchMock)

    const response = await apiClient.get('/databases')

    expect(response.data).toEqual([{ id: 1 }])
    expect(fetchMock).toHaveBeenCalledWith('/api/databases', expect.objectContaining({
      headers: expect.objectContaining({ Authorization: expect.stringMatching(/^Bearer /) }),
    }))
  })

  it('expose un conflit expected_version cohérent', async () => {
    localStorage.setItem('xmlforge_token', token())
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      success: false,
      message: 'Conflit de version: attendu 2, version courante 3',
      errors: { code: 'SYNC_CONFLICT', details: { current_version: 3 } },
    }, 409)))

    await expect(apiClient.post('/databases/1/query', { sql: 'UPDATE t SET x=1 WHERE id=1', expected_version: 2 }))
      .rejects.toMatchObject({ status: 409, code: 'SYNC_CONFLICT', isConflict: true })
  })

  it('supprime la session sur 401', async () => {
    localStorage.setItem('xmlforge_token', token())
    localStorage.setItem('xmlforge_user', '{}')
    const unauthorized = vi.fn()
    window.addEventListener('xmlforge:unauthorized', unauthorized)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ message: 'Token invalide' }, 401)))

    await expect(apiClient.get('/me')).rejects.toBeInstanceOf(ApiError)
    expect(localStorage.getItem('xmlforge_token')).toBeNull()
    expect(unauthorized).toHaveBeenCalled()
  })
})
