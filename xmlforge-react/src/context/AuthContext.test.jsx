import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ user: null }))

vi.mock('../services/authService', () => ({
  authService: {
    getStoredUser: () => mocks.user,
    me: async () => mocks.user,
    login: vi.fn(), register: vi.fn(), logout: vi.fn(),
  },
}))
vi.mock('../services/api', () => ({
  default: { getToken: () => 'valid', isTokenExpired: () => false, clearSession: vi.fn() },
}))
vi.mock('../services/socketService', () => ({
  socketService: { connect: vi.fn(), disconnect: vi.fn() },
}))

import { AuthProvider, useAuth } from './AuthContext'

function Probe() {
  const { isAdmin, roles, loading } = useAuth()
  return <div>{loading ? 'loading' : `${isAdmin}:${roles.join(',')}`}</div>
}

describe('rôles backend', () => {
  it("ne transforme plus l'adresse nyx en administrateur", async () => {
    mocks.user = { id: 1, email: 'nyx@xmlforge.io', role: 'user', is_admin: false }
    render(<AuthProvider><Probe /></AuthProvider>)
    await waitFor(() => expect(screen.getByText('false:USER')).toBeInTheDocument())
  })

  it('reconnaît le rôle admin fourni par Flask', async () => {
    mocks.user = { id: 2, email: 'admin@example.com', role: 'admin', is_admin: true }
    render(<AuthProvider><Probe /></AuthProvider>)
    await waitFor(() => expect(screen.getByText('true:ADMIN')).toBeInTheDocument())
  })
})
