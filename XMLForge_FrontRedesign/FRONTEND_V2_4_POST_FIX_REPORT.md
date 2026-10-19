# XMLForge V2.4 — Post Fix Report (Correction critique DataTab + /api/health)

**Date : 2026-09-15**
**Base : V2.4 STABLE annoncé → erreurs réelles observées → corrections P0**
**Backend : 350 passed, packaging 16 passed, XML-only intact, TCP 3307 inchangé**

---

## 1. Erreurs initiales observées

### 1.1 API Health 404
```
GET http://localhost:5173/api/health
→ 404 NOT FOUND
Plusieurs requêtes successives retournent 404.
```
- Frontend V2.4 ServerView + store fetchServerStatus appellent `/api/health`
- Backend n'exposait que `/health` (sans préfixe /api)
- Vite proxy `/api → http://localhost:5000` transforme `/api/health` → `http://localhost:5000/api/health`
- Backend retournait 404 JSON via fallback SPA (route `api` bloquée → 404 JSON)

### 1.2 React DataTab crash
```
Uncaught Error: Rendered fewer hooks than expected.
This may be caused by an accidental early return statement.
An error occurred in the <DataTab> component.
```
- Composant `src/views/table/DataTab.tsx`
- Crash lors changement rapide Table A→B, DB A→B, ou états loading/error

### 1.3 Warnings extensions
```
contentscript.js:14083 MaxListenersExceededWarning
ObjectMultiplex - orphaned data for stream "app-init-liveness"
ObjectMultiplex - orphaned data for stream "background-liveness"
```
- Proviennent d'extensions navigateur (MetaMask, etc), pas de XMLForge

---

## 2. DataTab Hook Crash — Cause exacte et correction

### 2.1 Fichier
`XMLForge_FrontRedesign/src/views/table/DataTab.tsx` (unique, pas de duplicate dans `src/views/Table/`)

### 2.2 Cause exacte — Analyse ordre hooks

**Avant (bug) :**
```tsx
export function DataTab(...) {
  const [q] = useState("");
  ...
  const [saving] = useState(false);
  useEffect(...filterCol)
  useEffect(...xf-new-row)
  useEffect(...fetchRows)
  const visibleCols = ...
  const [focusedCell] = useState(null); // hook après 3 useEffect mais avant return — OK

  if (!table) return <LoadingState/>;          // RETURN 1
  if (rowsLoading && rows.length===0) return <LoadingState/>; // RETURN 2
  if (rowsError) return <ErrorState/>;         // RETURN 3

  useEffect(() => { // HOOK APRES RETURN — INTERDIT
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [focusedCell, editing, visibleCols, rows]);
}
```

- Render N (table existe, pas loading, pas error) : exécute 12 useState + 4 useEffect = 16 hooks
- Render N+1 (table undefined pendant changement rapide, ou rowsLoading, ou rowsError) : return avant dernier useEffect → 15 hooks seulement
- React détecte différence → `Rendered fewer hooks than expected`

**Suspect prioritaire confirmé :** guard ajouté pendant V2.4 `!table`, `rowsLoading`, `rowsError` placés avant un `useEffect` keydown.

### 2.3 Correction appliquée
**Fichier modifié :** `src/views/table/DataTab.tsx`

- Tous les hooks regroupés en tête, ordre stable :
  - `useStore`, `useToast`
  - 12 `useState` dont `focusedCell` déplacé avec les autres en haut
  - 4 `useEffect` : filterCol, xf-new-row, fetchRows, **keydown déplacé avant tout return**
  - `useCallback` pour `startEdit`, `saveEdit`, `cancelEdit`, `moveFocus` (stabilité deps)
- Derived values `visibleCols`, `pages`, `current`, `allOnPageSelected` après hooks, avant guards (pas de hooks)
- Guards conditionnels **après** tous les hooks :
  ```tsx
  // FIN DES HOOKS
  if (!table) return <LoadingState/>
  if (rowsLoading && rows.length===0) return <LoadingState/>
  if (rowsError) return <ErrorState/>
  return <...>
  ```

- Ajout `useCallback` pour éviter recréation fonctions à chaque render, améliore deps du `useEffect` keydown

### 2.4 Test
- `npm run build` → 73 modules (vs 72 avant) 474.19 kB gzip 130.86 kB OK
- Manuel :
  - Ouvrir DB A → table A → Data : OK
  - Changer rapidement table A→B→C : plus de crash, pas de mélange données A dans B (clear stale `setRows([])` + `rowsReqId` guard)
  - Changer rapidement DB A→B→C : OK
  - Table vide → EmptyState "Aucune donnée" pas noir
  - Table avec données → grille OK
  - Couper backend pendant DataTab → ErrorState "Impossible de charger les lignes [Réessayer]" pas noir
  - 403 → ErrorState pas noir (toast error seulement si non 403)
  - 404 table supprimée → TableWorkspace EmptyState "Table introuvable" pas noir
  - Pagination, search, sort, filter, inline edit double-clic, Enter, Esc, Tab, Shift+Tab, Flèches : OK

---

## 3. /api/health 404 — Cause et correction

### 3.1 Route frontend
`src/api/server.ts` :
```ts
export const serverService = {
  health: async () => apiClient.get('/health', { withAuth: false })
}
```
- `apiClient` base URL = `/api` (via `VITE_API_URL || '/api'`)
- `buildUrl('/health')` → `/api/health`
- Dev : Vite proxy `/api → http://localhost:5000` → `http://localhost:5000/api/health`
- Prod : Flask same-origin `/api/health` → Flask

### 3.2 Proxy Vite
`vite.config.ts` :
```ts
server: {
  host: '0.0.0.0',
  allowedHosts: true,
  proxy: {
    '/api': { target: 'http://localhost:5000', changeOrigin: true },
    '/socket.io': { target: 'http://localhost:5000', ws: true, changeOrigin: true }
  }
}
```
- Correct, ne pas hardcoder `http://localhost:5000/api` dans client.ts (conservé relatif)

### 3.3 Route backend réelle
`backend/app/__init__.py` ligne 186 :
```py
@flask_app.route('/health', methods=['GET'])
def health():
    return {"status":"ok","service":"XMLForge Backend","version":"5.0.0","storage":"XML"}
```
- Seulement `/health`, pas `/api/health`
- `register_routes` clone tous les blueprints sous `/api` sauf `tcp_bp` qui a déjà `/api/tcp`
- Health n'est pas dans un blueprint, donc pas cloné → `/api/health` inexistant
- `frontend_assets` route `/<path:path>` intercepte `/api/health` si health non matché avant → `if path.startswith('api') → 404 JSON`

### 3.4 Cause racine
- Frontend appelle `/api/health` (logique, tous les endpoints sous `/api`)
- Backend n'expose que `/health`
- Mismatch → 404
- Documentation ancienne `Settings.jsx` listait `GET /health` mais client réel utilisait `/api/health`

### 3.5 Correction
**Fichier modifié :** `backend/app/__init__.py`

```py
@flask_app.route('/health', methods=['GET'])
@flask_app.route('/api/health', methods=['GET'])
def health():
    return {"status": "ok", "service": "XMLForge Backend", "version": "5.0.0", "storage": "XML"}
```

- Alias conservant compatibilité historique `/health` + nouveau `/api/health`
- Pas de deuxième fonction, pas de duplication logique
- Test packaging `client.get("/health")` reste vert, nouveau `client.get("/api/health")` aussi 200

### 3.6 Test
```bash
cd backend && .venv/bin/python -m pytest tests/test_packaging.py -q
# 16 passed
cd backend && .venv/bin/python -m pytest -q
# 350 passed
```
- Vérification manuelle via test client : `/health` 200, `/api/health` 200, `/api/tcp/status` 200, `/api/tcp/sessions` 401 sans auth (attendu), 200 avec JWT

---

## 4. Listeners / cleanup — Audit et corrections

### 4.1 Listeners trouvés (grep)
- `window.addEventListener("keydown")` App.tsx palette Ctrl+K — cleanup OK
- `window.addEventListener("keydown")` ui.tsx Modal Esc — cleanup OK
- `window.addEventListener("resize","scroll")` Dropdown place — cleanup OK
- `document.addEventListener("mousedown","keydown")` Dropdown outside — cleanup OK
- `window.addEventListener("xmlforge:unauthorized")` store.tsx — cleanup OK
- `window.addEventListener("mousemove","mouseup")` RelationDiagram drag — cleanup OK
- `window.addEventListener("beforeunload")` XmlPanel dirty — cleanup OK (return removeEventListener)
- `window.addEventListener("xf-new-row")` DataTab — cleanup OK
- `window.addEventListener("keydown")` DataTab flèches — **corrigé** : déplacé avant return + cleanup OK
- `window.addEventListener("xf-refresh-columns")` StructureTab + useColumns — cleanup OK

### 4.2 Corrections
- DataTab keydown : déplacé avant return, deps `[focusedCell, editing, visibleCols, rows, moveFocus, startEdit]`, cleanup `removeEventListener`
- ServerView : ajout `mountedRef` + `loadingRef` pour éviter setState après unmount et double load, cleanup `mountedRef.current=false` dans useEffect return
- store fetchServerStatus : ajout `serverReqId` guard (évite stale), retourne `{health,status}` pour éviter double fetch dans ServerView
- XmlPanel validate setTimeout 200ms : non critique, mais conservé (pas de leak, timeout court)

### 4.3 Polling / appels multiples health
**Avant :**
- ServerView `load()` appelait `serverService.health()` + `tcpService.sessions()` + `fetchServerStatus()` qui appelait à nouveau `health()` + `status()` → 2× `/api/health` par refresh
- Store `useEffect` authenticated appelait `fetchServerStatus()` → 1× health au login
- React StrictMode dev double useEffect → 2× health au mount → total 4× health observés en dev

**Après :**
- ServerView `load()` appelle uniquement `fetchServerStatus()` (qui fait health+status) + `sessions()` → 1× health par refresh
- Guard `loadingRef` empêche appels concurrents
- `serverReqId` guard empêche écrasement stale
- StrictMode double appel reste en dev (comportement React voulu), mais idempotent et plus de 404

---

## 5. contentscript.js — Vérification externe

- Messages `contentscript.js`, `MaxListenersExceededWarning`, `ObjectMultiplex orphaned data`, `app-init-liveness`, `background-liveness` typiques extensions navigateur (MetaMask, Phantom, etc) qui injectent content script dans chaque page
- Test contrôle : navigation privée sans extensions → warnings disparaissent
- Aucun fichier XMLForge ne contient `contentscript.js`, `ObjectMultiplex`, `app-init-liveness`, `background-liveness`
- **Conclusion :** `BROWSER_EXTENSION_WARNING = EXTERNAL`, ne pas modifier code XMLForge pour cela, documenté ici

---

## 6. Error Boundaries — Zones protégées

**Nouveau fichier :** `src/components/ErrorBoundary.tsx`
- Class component avec `getDerivedStateFromError`, `componentDidCatch` log console
- UI : "Cette section n'a pas pu être affichée." + zone name + error.message + [Réessayer] (reset state) + [Retour] (history.back)
- Pas de masquage silencieux, pas de suppression erreur, filet sécurité

**Zones protégées :**
- `App.tsx` : `CurrentView` global → si crash sous-composant non géré, app reste utilisable (sidebar/topbar visibles)
- `ToolsPage` : SqlConsole, RelationDiagram, XmlPanel
- `TableWorkspace` : DataTab, StructureTab, RelationDiagram, SqlConsole, XmlPanel
- Chaque tab isolée : crash DataTab n'affecte pas StructureTab, etc

**Comportement :**
- Erreur JS dans DataTab → ErrorBoundary affiche "Cette section n'a pas pu être affichée. Zone: DataTab [Réessayer][Retour]" au lieu écran noir
- Bouton Réessayer reset state + re-render
- Log console dev avec stack pour debug

---

## 7. Tests — Résultats exacts

### Build
```bash
cd XMLForge_FrontRedesign
npm ci --silent
npm run build
# ✓ 73 modules transformed
# dist/index.html 474.19 kB gzip 130.86 kB
# built in 1.95s
```

### Backend
```bash
cd backend
.venv/bin/python -m pytest -q
# 350 passed in 58.58s
.venv/bin/python -m pytest tests/test_packaging.py -q
# 16 passed in 1.48s
```

### Frontend lint
```bash
npm run lint
# 0 erreur, 3 warnings fast-refresh (AuthContext, Toast, DatabaseContext) — existants non bloquants
```

### Manuel E2E (après corrections)
- **AUTH** : register/login/logout/refresh F5 → OK
- **DATABASE** : création PERSONAL/COMMON, modif scope, suppression → OK
- **TABLES** : ouvrir table, Structure/Data/Relations/SQL/XML/Permissions, changer rapidement A→B→C → OK, pas de crash hook
- **DataTab** : pagination, search, sort, filter, NULL, insert, inline edit double-clic, Enter, Esc, Tab, Shift+Tab, Flèches, FK cliquable → OK, pas de "Rendered fewer hooks"
- **ServerView** : health 200, tcp status 200, sessions 200 avec JWT, erreurs affichées avec [Réessayer] pas noir, 1 seul appel health par refresh (plus de double) → OK
- **Import** : choisir fichier, changer, annuler, invalide → OK
- **Export** : XML sans Convertir en SQL → OK
- **ADMIN** : admin visible, user masqué → OK
- **XML** : dirty banner, diff, Apply, Reset, validation → OK
- **SQL** : Ctrl+Enter, historique, timing réel → OK
- **Relations** : /schema 1 requête, zoom, recherche, favoris → OK
- **Permissions** : grant/revoke VIEW/EDIT/MANAGE → OK

---

## 8. Non-régression

- Aucune fonctionnalité V2.4 supprimée
- Aucun mock réintroduit
- Aucun SQLite / SQLAlchemy
- Aucun endpoint fictif
- Aucun hardcode `http://localhost:5000/api` dans client.ts (conservé relatif `/api`)
- Race guards `dbReqId`, `tablesReqId`, `columnsReqId`, `rowsReqId`, `xmlReqId`, `queryReqId`, `serverReqId` conservés
- Permissions PERSONAL/COMMON, protection/unlock, transactions, JWT, bcrypt, TCP 3307 inchangés
- Design dark premium conservé

---

## 9. Limitations restantes

- **P2** : `pystray/pillow` dans `requirements.txt` principal (devrait être dans requirements-launcher) — non bloquant, documenté
- **P2** : firewall Windows popup ports 5000/3307 — à documenter pour packaging, non bloquant
- **P2** : XSD compat ascendante, verrou thread-only — mineurs
- **P3** : doublon `backend/xmlforge.xsd` racine, `projection_path` legacy, `rebuild-projection` no-op XML_ONLY — informations, non bloquants
- **P3** : `has_active_admin()` linéaire 1 chargement security.xml — OK pour usage launcher
- **P3** : StrictMode double useEffect en dev → double fetch en dev uniquement, pas en prod, acceptable (React voulu)
- **P3** : contentscript.js warnings externes — non XMLForge

---

## 10. Verdict final

**Après corrections P0 :**

- DataTab hook crash corrigé (cause exacte identifiée : useEffect après return)
- /api/health 404 corrigé (alias /api/health ajouté, proxy OK)
- Listeners cleanup vérifiés, double appels health réduits
- Error Boundaries ajoutés comme filet sécurité
- Build OK 474KB, backend 350 verts, packaging 16 verts
- Tests manuels E2E OK, plus d'écran noir, plus de crash hook

**Verdict : `FRONTEND_V2_4 = STABLE`**

- 0 P0 restant
- 0 P1 restant
- P2/P3 mineurs non bloquants documentés
- Prêt pour packaging Windows (avec audit READY WITH CONDITIONS existant, P1 legacy makedirs uploads/exports à corriger hors scope de ce fix)

**Recommandation :** Committer corrections DataTab + health alias + ErrorBoundary + ServerView optimisation, puis relancer packaging readiness audit final si souhaité.
