import { useNavigate } from 'react-router-dom'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { TCPCredentials } from '../../components/TCPCredentials/TCPCredentials'

const endpoints = [
  ['POST', '/api/register', 'Inscription (rôle USER par défaut)'],
  ['POST', '/api/login', 'Connexion (JWT)'],
  ['GET', '/api/me', 'Profil de l’utilisateur connecté'],
  ['POST', '/api/logout', 'Révocation du token'],
  ['GET', '/api/databases', 'Bases accessibles (PERSONAL / COMMON)'],
  ['POST', '/api/databases', 'Création de base (scope PERSONAL/COMMON)'],
  ['GET', '/api/databases/:id', 'Détail d’une base'],
  ['PUT', '/api/databases/:id', 'Renommage / description / scope'],
  ['DELETE', '/api/databases/:id', 'Suppression (admin requis)'],
  ['POST', '/api/databases/:id/archive', 'Archivage (admin requis)'],
  ['POST', '/api/databases/:id/restore', 'Restauration (admin requis)'],
  ['POST', '/api/databases/:id/query', 'SQL SELECT/INSERT/UPDATE/DELETE'],
  ['POST', '/api/databases/:id/sync-xml', 'Synchronisation depuis XML'],
  ['GET', '/api/databases/:id/permissions', 'Liste des partages de la base'],
  ['POST', '/api/databases/:id/permissions', 'Partager la base (VIEW/EDIT/MANAGE)'],
  ['DELETE', '/api/databases/:id/permissions/:userId', 'Retirer un partage'],
  ['GET', '/api/tables/:databaseId', 'Tables d’une base'],
  ['POST', '/api/tables', 'Création de table'],
  ['PUT', '/api/tables/:id', 'Modification de table'],
  ['DELETE', '/api/tables/:id', 'Suppression de table'],
  ['POST', '/api/tables/:id/archive', 'Archivage de table'],
  ['POST', '/api/tables/:id/restore', 'Restauration de table'],
  ['GET', '/api/tables/:id/permissions', 'Permissions de la table'],
  ['POST', '/api/tables/:id/permissions', 'Partager une table'],
  ['GET', '/api/tables/:id/rows', 'Lignes paginées + recherche/tri'],
  ['POST', '/api/tables/:id/rows', 'Ajout de ligne'],
  ['PUT', '/api/tables/:id/rows/:rowId', 'Modification de ligne'],
  ['DELETE', '/api/tables/:id/rows/:rowId', 'Suppression de ligne'],
  ['GET', '/api/columns/:tableId', 'Colonnes d’une table'],
  ['POST', '/api/columns', 'Création de colonne'],
  ['PUT', '/api/columns/:id', 'Modification de colonne'],
  ['DELETE', '/api/columns/:id', 'Suppression de colonne'],
  ['POST', '/api/import/xml', 'Import XML (nouvelle base)'],
  ['POST', '/api/import/sql', 'Import SQL (nouvelle base)'],
  ['POST', '/api/import/project', 'Import projet complet'],
  ['GET', '/api/export/xml/:id', 'Export XML (admin requis)'],
  ['GET', '/api/export/sql/:id', 'Export SQL'],
  ['GET', '/api/export/table-xml/:id', 'Export XML de table (admin requis)'],
  ['GET', '/api/export/table-sql/:id', 'Export SQL de table'],
  ['GET', '/api/export/project/:id', 'Export projet complet'],
  ['POST', '/api/convert/xml-to-sql', 'Conversion XML → SQL'],
  ['POST', '/api/convert/sql-to-xml', 'Conversion SQL → XML'],
  ['POST', '/api/unlock-table', 'Déverrouillage d’une table protégée'],
  ['GET', '/api/unlocks', 'Déverrouillages de session'],
  ['DELETE', '/api/unlocks', 'Révoquer ses déverrouillages'],
  ['GET', '/api/users', 'Utilisateurs (admin requis)'],
  ['POST', '/api/users', 'Création d’utilisateur (admin)'],
  ['PUT', '/api/users/:id', 'Modification d’utilisateur (admin)'],
  ['DELETE', '/api/users/:id', 'Suppression d’utilisateur (admin)'],
  ['POST', '/api/users/:id/reset-password', 'Réinitialiser un mot de passe (admin)'],
  ['POST', '/api/users/:id/toggle-active', 'Activer/désactiver (admin)'],
  ['GET', '/api/history', 'Historique métier (admin requis)'],
  ['GET', '/api/audit-logs', 'Journal d’audit (admin requis)'],
  ['GET', '/api/tcp/status', 'Statut du serveur TCP (sans JWT)'],
  ['GET', '/api/tcp/credentials', 'Identifiants TCP de l’utilisateur'],
  ['POST', '/api/tcp/credentials/regenerate', 'Régénérer le secret TCP'],
  ['POST', '/api/tcp/credentials/show-password', 'Régénérer + afficher (avec mot de passe web)'],
  ['GET', '/api/tcp/sessions', 'Sessions TCP actives'],
  ['GET', '/health', 'Santé du backend (sans JWT)'],
]

export function SettingsPage() {
  const navigate = useNavigate()
  return (
    <div className="screen active" id="screen-api">
      <aside className="sidebar"><Sidebar active="api" /></aside>
      <div className="dash-main">
        <div className="page-header">
          <a className="back-link" href="#" onClick={event => { event.preventDefault(); navigate('/dashboard') }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
            Bases de données
          </a>
        </div>
        <div className="dash-content">
          <div className="dash-head"><div><h1>Paramètres — API & connexions externes</h1><p>Connexions TCP/IP, clés API et accès externes à XMLForge</p></div></div>

          <div className="rel-section-title">Connexion TCP/IP</div>
          <div className="api-card"><TCPCredentials /></div>

          <div className="rel-section-title" style={{ marginTop: 26, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}><span>Clés API</span><button className="btn btn-sm" disabled>Générer une clé</button></div>
          <div className="info-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg><span>Le backend actuel ne fournit pas de gestion de clés API. Aucun token fictif n’est généré par le frontend.</span></div>
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'auto', background: 'var(--card)' }}><table className="audit-table"><thead><tr><th>Libellé</th><th>Clé</th><th>Créée le</th><th>Dernière utilisation</th><th>Statut</th><th>Actions</th></tr></thead><tbody><tr><td colSpan={6}><div className="empty-state" style={{ padding: 24 }}><div className="es-title">Aucune clé API</div></div></td></tr></tbody></table></div>

          <div className="rel-section-title" style={{ marginTop: 26 }}>Endpoints — aperçu de référence</div>
          <div className="info-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg><span>Routes réellement exposées par le backend Flask actuel.</span></div>
          <div className="endpoint-list">{endpoints.map(([method, path, description]) => <div className="endpoint-row" key={path}><span className={`badge ${method === 'POST' ? 'badge-green' : method === 'PUT' ? 'badge-warn' : 'badge-blue'}`}>{method}</span><span>{path}</span><span className="dim">{description}</span></div>)}</div>
        </div>
      </div>
    </div>
  )
}
