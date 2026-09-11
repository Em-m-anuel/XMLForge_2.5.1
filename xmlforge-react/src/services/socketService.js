/**
 * SocketService - Prépare le frontend pour la collaboration temps réel
 * Ne modifie pas l'API REST, ajoute uniquement SocketIO
 */
import { io } from 'socket.io-client'
import { getSocketUrl } from './api'

class SocketService {
  constructor() {
    this.socket = null
    this.listeners = new Map()
  }

  connect(url) {
    if (import.meta.env.VITE_ENABLE_SOCKET_IO !== 'true') return null
    const baseUrl = url || getSocketUrl()
    if (this.socket) return this.socket

    this.socket = io(baseUrl, {
      // Le backend Flask-SocketIO actuel fonctionne de manière portable en
      // polling/threading. Ne pas forcer un upgrade WebSocket non configuré.
      transports: ['polling'],
      autoConnect: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
    })

    this.socket.on('connect', () => {
      console.log('[SocketIO] Connecté', this.socket.id)
    })

    this.socket.on('disconnect', () => {
      console.log('[SocketIO] Déconnecté')
    })

    // Écoute générique
    this.socket.on('xmlforge_event', (payload) => {
      // payload: {type, data}
      this.emitLocal(payload.type, payload.data)
    })

    // Événements spécifiques (relais vers listeners locaux)
    const events = ['new_database','new_table','new_column','modification','suppression','import_xml','export_xml','export_sql']
    events.forEach(ev => {
      this.socket.on(ev, (data) => {
        this.emitLocal(ev, data)
        this.emitLocal('xmlforge_event', { type: ev, data })
      })
    })

    return this.socket
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set())
    this.listeners.get(event).add(callback)
    // Retourne fonction unsubscribe
    return () => this.off(event, callback)
  }

  off(event, callback) {
    if (!this.listeners.has(event)) return
    this.listeners.get(event).delete(callback)
  }

  emitLocal(event, data) {
    if (!this.listeners.has(event)) return
    this.listeners.get(event).forEach(cb => {
      try { cb(data) } catch (e) { console.error('[SocketService] listener error', e) }
    })
  }

  // Helper pour émettre depuis client (si besoin futur)
  emit(event, data) {
    if (this.socket) this.socket.emit(event, data)
  }
}

export const socketService = new SocketService()
export default socketService
