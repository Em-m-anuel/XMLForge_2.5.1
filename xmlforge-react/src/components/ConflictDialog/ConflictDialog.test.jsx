import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ConflictDialog } from './ConflictDialog'

describe('ConflictDialog', () => {
  it('explique le 409 et propose le rechargement sans écrasement', () => {
    const reload = vi.fn()
    render(<ConflictDialog open onReload={reload} onClose={vi.fn()} />)
    expect(screen.getByText(/modifiée depuis votre dernière synchronisation/i)).toBeInTheDocument()
    fireEvent.click(screen.getByText(/Recharger la version récente/i))
    expect(reload).toHaveBeenCalledOnce()
  })
})
