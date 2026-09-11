import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('./AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true }) }))
vi.mock('../services/unlockService', () => ({
  unlockService: {
    list: vi.fn().mockResolvedValue([{ table_id: 42, is_expired: false }]),
    clear: vi.fn(),
  },
}))

import { DatabaseProvider, useDatabaseContext } from './DatabaseContext'

function Probe() {
  const { isUnlocked, unlockedTableIds } = useDatabaseContext()
  return <div>{`${isUnlocked(42)}:${unlockedTableIds.join(',')}`}</div>
}

describe('déverrouillage individuel', () => {
  it('restaure uniquement les IDs confirmés par le backend, jamais la clé', async () => {
    sessionStorage.setItem('xmlforge_unlocks', JSON.stringify(['999']))
    render(<DatabaseProvider><Probe /></DatabaseProvider>)
    await waitFor(() => expect(screen.getByText('true:42')).toBeInTheDocument())
    expect(sessionStorage.getItem('xmlforge_unlocks')).toBe('["42"]')
    expect(sessionStorage.getItem('xmlforge_db_key')).toBeNull()
  })
})
