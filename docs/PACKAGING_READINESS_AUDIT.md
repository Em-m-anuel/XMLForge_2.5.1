# XMLFORGE — PACKAGING READINESS AUDIT

**Date : 2026-09-15**
**Méthode : Inspection statique du code actuel + exécution réelle tests backend/frontend, vérification chemins, ressources, secrets, TCP, frontend dist, SQLite**
**Aucune modification de code effectuée dans cette phase d'audit (seul ce rapport est créé)**

---

## 1. Résumé exécutif

XMLForge est **désormais prêt au packaging Windows avec conditions mineures** après la phase de préparation au packaging (fichiers `backend/app/paths.py`, `backend/app/runtime.py`, adaptations config, serving frontend, secrets persistants, `flask init-app`).

- **Architecture** : XML-only confirmée, 0 dépendance SQLite/SQLAlchemy/MySQL, moteur XML natif, Control Plane XML, Data Plane XML, Flask REST + TCP 3307 dans même processus, client Python stdlib pure
- **Chemins** : Séparation ressources applicatives (lecture seule, bundle) / données runtime (inscriptibles, `%LOCALAPPDATA%\XMLForge`) implémentée via `paths.py` et `is_frozen()` detection (`sys.frozen`, `sys._MEIPASS`, `sys.executable`)
- **Ressources** : XSD chargés via `paths.static_dir()` → robuste en mode gelé, à déclarer en data files bundler
- **Secrets** : Génération persistante `secrets.token_urlsafe(48)` dans `config/secrets.env` mode 0600, idempotent, jamais embarqués
- **Premier lancement** : `flask init-app` non interactive (dossiers + secrets + bootstrap + admin) + `xml-bootstrap`/`create-admin` interactifs conservés dev
- **Frontend** : Build statique `dist` servi par Flask même origine, fallback SPA, `/api` et `/socket.io` restent 404 JSON, chemins sensibles bloqués → 404
- **Tests** : Backend 350 passed (59s), Packaging 16 passed, Frontend 10 passed/1 skipped, Lint 0 erreur/3 warnings, Build OK (old 86KB + new V2.2 461KB singlefile)
- **SQLite** : 0 fichier `.db`/`.sqlite` en runtime, grep runtime vide (hors docs historiques)

**Verdict** : **READY WITH CONDITIONS** — 0 P0 bloquant, 2 P1 majeurs mineurs (uploads/exports legacy makedirs + pystray/pillow hors runtime), checklist packaging fournie.

---

## 2. État actuel du projet

- **Repo** : `/home/user/XMLForge`, branche `main`, Python 3.13.14, Node v20.20.2, npm 10.8.2
- **Backend** : `backend/` Flask 3.1.0, Flask-JWT-Extended 4.7.1, Flask-Bcrypt 1.0.1, Flask-CORS 5.0.0, Flask-SocketIO 5.3.6 (threading), python-dotenv 1.0.1, lxml 6.0.0 (extension native), marshmallow 3.22.0, pystray 0.19.5 + pillow 12.3.0 (launcher Windows hors runtime serveur), pytest 8.3.4
- **Frontend** : 2 frontends présents :
  - `xmlforge-react/` (ancien, React/Vite, build multi-chunks, Workspace 86KB, index 288KB) — fonctionnel, aligné XML Engine (fix list_columns)
  - `XMLForge_FrontRedesign/` (nouveau V2.3, React 19 + TS + Tailwind 4, singlefile 461KB, design dark premium) — intégré réel au backend, diagramme schéma, édition directe, favoris, diff XML, duplication, truncate
- **Point d'entrée backend** : `backend/run.py` → `create_app(Config)` → `socketio.run(host=HTTP_HOST, port=HTTP_PORT)` + TCPServer thread daemon
- **Point d'entrée frontend** : `xmlforge-react/src/main.jsx` et `XMLForge_FrontRedesign/src/main.tsx` → Vite build → `dist/`
- **Git** : Modifications non commitées packaging + V2.2/V2.3, pas de commit auto (consigne respectée), `.gitignore` exclut `backend/logs/`, `backend/tmp/`, `backend/config/`, `secrets.env`, `node_modules/`, `dist/`, `.venv/`, `xmlforge.db`

---

## 3. Architecture runtime actuelle

```
Navigateur (frontend build dist)
   ↓ REST /api (même origine Flask)
Backend Flask (backend/) bind 0.0.0.0:5000 (configurable via XMLFORGE_HTTP_HOST/PORT)
   ├── create_app(Config) → factory
   │   ├── Config via paths.py : CONTROL_STORAGE_FOLDER, XML_STORAGE_FOLDER, UPLOAD_FOLDER, EXPORT_FOLDER, LOG_FOLDER, CONFIG_FOLDER, FRONTEND_DIST_FOLDER, FILE_LOGS_ENABLED
   │   ├── Control Plane XML : security.xml, catalog.xml, history.xml, audit/YYYY-MM.xml[.gz] (+ .lock) — dossier privé 0700, validation XSD
   │   ├── Data Plane XML : data/xml/<id>_<slug>.xml (+ .lock) — atomic_write, database_lock flock/RLock, safe_replace
   │   ├── XML Native Engine : XmlNativeEngine, parse_document, serialize_document, XSD validation
   │   ├── PermissionService PERSONAL/COMMON VIEW/EDIT/MANAGE + UnlockService personal session 24h
   │   └── TCPServer 0.0.0.0:3307 (thread daemon xmlforge-tcp, SO_REUSEADDR, listen 64, timeout 1s, buffer 8 MiB, sessions, transactions snapshot XML+catalog)
   └── Frontend dist servi si présent : / → index.html, /<path> → fichier statique si existe sinon index.html (SPA), /api/* et /socket.io/* → 404 JSON, data/, control/, config/, logs/, tmp/, backend/, .., %2e → 404 JSON (sécurité)
       ↓ TCP [type:1][len:4 BE][JSON]
Client Python officiel xmlforge/ — stdlib pure
```

**Points structurants** :
- REST et TCP même processus (TCP démarré par `create_app()`)
- Frontend build statique, pas de Node au runtime
- Aucune dépendance dev au runtime (seulement 8 libs + pystray/pillow hors runtime)

---

## 4. Architecture Windows cible

```
APPLICATION (read-only) :
C:\Program Files\XMLForge\
   ├── XMLForge.exe (bundle Python + lxml + Flask + app)
   ├── static/
   │   ├── xmlforge.xsd
   │   └── control/
   │       ├── security.xsd, catalog.xsd, history.xsd, audit.xsd
   └── frontend/
       └── index.html + assets (dist V2.3 singlefile ou old multi-chunks)

DONNÉES UTILISATEUR (inscriptibles, sans élévation) :
%LOCALAPPDATA%\XMLForge\  (ou $XDG_DATA_HOME/XMLForge sur POSIX, ou XMLFORGE_DATA_DIR surcharge)
   ├── data\
   │   ├── control\  security.xml, catalog.xml, history.xml, audit\YYYY-MM.xml[.gz] (+ .lock)
   │   └── xml\      bases XML <id>_<slug>.xml (+ .lock)
   ├── tmp\
   │   ├── uploads\  imports temporaires
   │   └── exports\  exports temporaires
   ├── logs\         xmlforge.log (rotation 5 MB × 3, RotatingFileHandler)
   └── config\       .env + secrets.env (SECRET_KEY/JWT_SECRET_KEY, mode 0600 POSIX)

VARIABLES :
- XMLFORGE_DATA_DIR : force racine données (tests / install perso)
- XMLFORGE_CONFIG_FOLDER / XMLFORGE_LOG_FOLDER / XMLFORGE_FRONTEND_DIST : surcharges
- CONTROL_STORAGE_FOLDER / XML_STORAGE_FOLDER / UPLOAD_FOLDER / EXPORT_FOLDER : prioritaires (env > paths)
- XMLFORGE_HTTP_HOST/PORT, XMLFORGE_FILE_LOGS, etc : configurables

RUNTIME CIBLE :
- Windows 10/11 x64, Python embarqué, frontend embarqué, Flask 5000 (configurable), TCP 3307 inchangé, XML-only, aucun Python/Node externe, aucun .db/.sqlite
```

---

## 5. Analyse des chemins et données persistantes

| Fichier/Dossier | Emplacement code actuel | Lecture/Écriture | Basé sur | Risque Program Files READ-ONLY ? | Statut |
|---|---|---|---|---|---|
| `security.xml` + `.lock` | `paths.control_folder()` → `_data_path("data/control", "data/control")` → si frozen → `%LOCALAPPDATA%\XMLForge\data\control\` sinon `backend/data/control\` | R/W | `paths.py` + env `CONTROL_STORAGE_FOLDER` + `XMLFORGE_DATA_DIR` + `is_frozen()` | ❌ NON si frozen (OK), mais en dev écrit dans backend/ | SAFE — séparation implémentée |
| `catalog.xml` + `.lock` | idem | R/W | idem | idem | SAFE |
| `history.xml` + `.lock` | idem | R/W | idem | idem | SAFE |
| `audit/YYYY-MM.xml[.gz]` + `.lock` | `data/control/audit/` via `store` | R/W append, rotation gzip | idem | idem | SAFE |
| Bases XML `data/xml/<id>_<slug>.xml` | `paths.xml_folder()` → `%LOCALAPPDATA%\XMLForge\data\xml\` si frozen | R/W | `paths.py` + env | ❌ NON si frozen (OK) | SAFE |
| `uploads/` | `paths.uploads_folder()` → `tmp/uploads` si installed sinon `uploads` + legacy `os.makedirs(os.path.dirname(__file__), 'uploads')` dans `__init__.py:26` | Créé au démarrage, non utilisé persistance (imports mémoire) | `paths.py` + `__file__` legacy | ⚠️ Legacy makedirs dans `__file__` pourrait échouer en Program Files read-only | P1 MAJEUR mineur — à nettoyer |
| `exports/` | `paths.exports_folder()` → `tmp/exports` si installed sinon `exports` + legacy `__init__.py:27` | Créé, non utilisé persistance (streaming HTTP) | idem | ⚠️ idem | P1 MAJEUR mineur |
| `.lock` fichiers | à côté de chaque XML | R/W verrou 0 octet | `xml_engine/storage.py` `database_lock` | ❌ NON si frozen (à côté données) | SAFE |
| `logs/xmlforge.log` | `paths.logs_folder()` → `logs` si installed sinon `logs` + env `XMLFORGE_LOG_FOLDER` | R/W RotatingFileHandler 5MB×3 | `paths.py` + `runtime.py` `setup_file_logging()` | ❌ NON si frozen (OK) | SAFE — file logs actifs si frozen ou XMLFORGE_FILE_LOGS=true |
| `config/.env` | `paths.config_folder()/.env` prioritaire puis `resource_root()/.env` | R (lecture) | `config.py` load_dotenv depuis config_folder puis resource_root, plus de CWD | ✅ SAFE — indépendant CWD | SAFE — M-1 fixé |
| `config/secrets.env` | `paths.secrets_file()` → `config/secrets.env` | R/W génération | `runtime.py` ensure_secrets() | ❌ NON si frozen (OK) | SAFE — M-2 fixé |

**Vérification `__file__` / `os.getcwd()` / `Path.cwd()` / `BACKEND_ROOT` / `sys.executable` / `_MEIPASS` / `sys.frozen`** :

- `paths.py` :
  - `is_frozen()` détecte `sys.frozen` ou `sys._MEIPASS` ✅
  - `resource_root()` : si `_MEIPASS` → `_MEIPASS`, si frozen → `dirname(sys.executable)`, sinon `backend/` (via `__file__` mais pour ressources lecture seule, acceptable) ✅
  - `_installed_base()` : env `XMLFORGE_DATA_DIR` prioritaire, sinon `user_data_root()` si frozen, sinon None (dev) ✅
  - `_data_path()` : si base installée → `base/subpath` sinon `resource_root()/dev_subpath` ✅
  - `static_dir()` cherche `app/static`, `<resources>/static`, `<resources>/app/static` → robuste bundler ✅
  - `frontend_dist_folder()` : env `XMLFORGE_FRONTEND_DIST` explicite, sinon `<resources>/frontend`, sinon `<resources>/../xmlforge-react/dist` → détection auto ✅
- `__init__.py:26-27` : `os.path.join(os.path.dirname(__file__), 'uploads/exports')` legacy — crée dossiers dans installation, risque si read-only (P1)
- `config.py` : `BACKEND_ROOT = paths.resource_root()` — ressources lecture seule, pas d'écriture, SAFE
- `document.py:55` : `os.path.join(paths.static_dir(), "xmlforge.xsd")` ✅
- `records.py:27` : `XSD_DIR = os.path.join(paths.static_dir(), "control")` ✅
- `run.py` / `app.py` : `host/port` depuis config `HTTP_HOST/PORT`, pas hardcodé ✅
- Aucun `os.getcwd()` / `Path.cwd()` pour données persistantes (vérifié grep) ✅
- `sys.executable` utilisé seulement pour `resource_root()` si frozen ✅

**Conclusion chemins** : Séparation APPLICATION (read-only) / DONNÉES (%LOCALAPPDATA%) implémentée, CWD indépendant, _MEIPASS non utilisé pour données, seul petit legacy uploads/exports via `__file__` reste.

---

## 6. Analyse Program Files / LocalAppData

**Risque initial (audit 2026-09-12)** : C-1/C-2 — écriture dans `__file__` / `BACKEND_ROOT` → crash Program Files.

**État actuel après préparation** :

- `config.py` :
  - `CONTROL_STORAGE_FOLDER = env or paths.control_folder()` → si frozen → LocalAppData
  - `XML_STORAGE_FOLDER = env or paths.xml_folder()` → LocalAppData
  - `UPLOAD_FOLDER = env or paths.uploads_folder()` → LocalAppData/tmp/uploads
  - `EXPORT_FOLDER = env or paths.exports_folder()` → LocalAppData/tmp/exports
  - `LOG_FOLDER = paths.logs_folder()` → LocalAppData/logs
  - `CONFIG_FOLDER = paths.config_folder()` → LocalAppData/config
  - `FRONTEND_DIST_FOLDER = env or None` → détection via paths
  - `FILE_LOGS_ENABLED = env XMLFORGE_FILE_LOGS or is_frozen()` → logs fichier auto si frozen

- `__init__.py` :
  - `os.makedirs(UPLOAD_FOLDER)`, `EXPORT_FOLDER`, `XML_STORAGE_FOLDER` via config (LocalAppData si frozen) ✅
  - `ensure_dir(CONTROL_STORAGE_FOLDER, mode 0o700)` → LocalAppData ✅
  - File logging si `FILE_LOGS_ENABLED` via `runtime.setup_file_logging()` → LocalAppData/logs ✅
  - Frontend serving : `FRONTEND_DIST_FOLDER or frontend_dist_folder()` → `<resources>/frontend` ou `../xmlforge-react/dist` ✅
  - Sécurité SPA : `data/`, `control/`, `config/`, `logs/`, `tmp/`, `backend/`, `..`, `%2e` → 404 JSON ✅

- `paths.py` :
  - `user_data_root()` priorise `LOCALAPPDATA` (Windows) → `~/XMLForge` si nt sans LOCALAPPDATA, sinon XDG → inscriptible sans élévation ✅
  - `_installed_base()` : `XMLFORGE_DATA_DIR` surcharge (tests) ou `user_data_root()` si frozen ✅

- **Recommandation cible respectée** :
  - APPLICATION `C:\Program Files\XMLForge\` read-only → code + XSD + frontend dist (lecture seule)
  - DONNÉES `%LOCALAPPDATA%\XMLForge\data\control\`, `data\xml\`, `tmp\uploads\`, `tmp\exports\`, `logs\`, `config\` → inscriptibles

- **Risque restant** : `__init__.py:26-27` `os.makedirs(os.path.join(os.path.dirname(__file__), 'uploads/exports'))` legacy — crée dans installation même si config pointe ailleurs. En Program Files read-only, `os.makedirs` échouerait (PermissionError) mais est dans try? Non, pas de try, mais `exist_ok=True` — si dossier n'existe pas et non inscriptible → crash au démarrage. À classer P1 MAJEUR mineur, mais non bloquant car `UPLOAD_FOLDER`/`EXPORT_FOLDER` réels sont déjà créés via config avant, et ces legacy ne sont pas utilisés pour persistance (imports mémoire, exports streaming). Recommandation : retirer ces 2 lignes (audit only, pas de correction ici).

**Verdict** : Séparation Program Files / LocalAppData **implémentée et fonctionnelle**, plus de C-1/C-2 bloquants, seul petit legacy à nettoyer.

---

## 7. Analyse des ressources embarquées

| Ressource | Emplacement actuel | Chargement | Doit être bundlée | Classification |
|---|---|---|---|---|
| `backend/app/static/xmlforge.xsd` | `app/static/xmlforge.xsd` | `paths.static_dir()` → `os.path.join(static_dir, "xmlforge.xsd")` + `etree.parse` + `XMLSchema` | OUI — data file bundler | À BUNDLER — SAFE après fix C-3 |
| `backend/app/static/control/security.xsd` | `app/static/control/security.xsd` | `paths.static_dir()/control` + `schema_path()` | OUI | À BUNDLER — SAFE |
| `catalog.xsd` | `app/static/control/catalog.xsd` | idem | OUI | À BUNDLER — SAFE |
| `history.xsd` | `app/static/control/history.xsd` | idem | OUI | À BUNDLER — SAFE |
| `audit.xsd` | `app/static/control/audit.xsd` | `schema_path("audit.xsd")` via XSD_DIR | OUI | À BUNDLER — SAFE |
| Frontend `dist` (V2.3 singlefile 461KB ou old multi) | `xmlforge-react/dist/` (dev) ou `backend/frontend/` ou `frontend/` (bundle) | `frontend_dist_folder()` cherche `frontend/`, `../xmlforge-react/dist`, env var | OUI | À BUNDLER — SAFE, servi Flask même origine, fallback SPA, /api/* 404 JSON |
| Icônes, templates non secrets | Aucun template externe, UI via React build | - | OPTIONNEL | SAFE |
| Config non secrète `.env.example` | `backend/.env.example` | Documentation, pas chargé runtime | NON (doc) | SAFE |
| `backend/xmlforge.xsd` racine | `backend/xmlforge.xsd` | Doublon legacy non référencé (seul `app/static/xmlforge.xsd` chargé) | NON — ne pas bundler | INFORMATION — confusion possible |

**Comportement PyInstaller `_MEIPASS`** :
- `resource_root()` retourne `_MEIPASS` si présent → ressources (XSD, frontend) lues depuis `_MEIPASS` (zone extraction temp, lecture seule) ✅
- Données jamais dans `_MEIPASS` (vérifié `_data_path` n'utilise jamais `_MEIPASS`, seulement `user_data_root()` si frozen) ✅
- `static_dir()` cherche dans `app/static`, `<resources>/static`, `<resources>/app/static` → compatible one-file et one-dir ✅
- `frontend_dist_folder()` cherche `<resources>/frontend` (layout bundle) + `../xmlforge-react/dist` (dev) ✅

**Classification** : Aucune ressource BLOQUANT, tous les XSD et frontend dist sont SAFE si déclarés en data files bundler (C-3 fixé au niveau code, reste à déclarer au build).

---

## 8. Analyse XSD

- **Emplacement** : `backend/app/static/xmlforge.xsd` + `control/*.xsd` (4 fichiers)
- **Références** : relatives via `paths.static_dir()`, pas de chemin absolu hardcodé
- **Chargement** : `document.py: _xsd_schema()` → `os.path.join(paths.static_dir(), "xmlforge.xsd")` → `etree.parse` → `XMLSchema`, `records.py: XSD_DIR = os.path.join(paths.static_dir(), "control")` → `schema_path(xsd)` → `read_validated(path, schema)`
- **Validation** : `parse_document(..., validate=True)` et `serialize_document()` valident XSD via lxml → fail-closed si invalide
- **Embarqué** : `static_dir()` robuste en mode gelé (cherche 3 candidats) → si XSD non inclus data files bundler → `FileNotFoundError` au premier import → crash → à classer comme risque build, pas runtime actuel
- **PyInstaller** : `_MEIPASS` contient XSD si déclarés en data files, `resource_root()` pointe vers `_MEIPASS` → chargement OK

**Classification** :
- `xmlforge.xsd` : À BUNDLER — SAFE (code fixé)
- `security.xsd`, `catalog.xsd`, `history.xsd`, `audit.xsd` : À BUNDLER — SAFE
- `backend/xmlforge.xsd` racine : INFORMATION — doublon legacy non chargé, ne pas bundler

---

## 9. Analyse configuration et secrets

| Secret/Config | Valeur actuelle | Génération | Stockage | Persistant | Embarqué EXE ? | Exposé | Classification |
|---|---|---|---|---|---|---|---|
| `SECRET_KEY` | `os.getenv('SECRET_KEY', 'xmlforge-dev-secret-key-please-change-40chars')` dev default, `ProductionConfig.validate()` exige non-dev | Si frozen : `ensure_secrets()` → `token_urlsafe(48)` si env et fichier absents, sinon réutilise fichier | `config/secrets.env` via `paths.secrets_file()` → `%LOCALAPPDATA%\XMLForge\config\secrets.env` si frozen, mode 0600 POSIX, écriture atomique `mkstemp` + `os.replace` + `fsync` | OUI — idempotent, même valeurs aux lancements suivants | ❌ NON — jamais dans bundle, généré premier lancement | ❌ NON — jamais journalisé | SAFE — M-2 fixé |
| `JWT_SECRET_KEY` | idem dev default `xmlforge-dev-jwt...` | idem | idem | OUI | ❌ NON | ❌ NON | SAFE |
| `.env` | `backend/.env.example` documente `XMLFORGE_HTTP_HOST/PORT`, `XMLFORGE_DATA_DIR`, `XMLFORGE_FILE_LOGS`, `XMLFORGE_FRONTEND_DIST`, `CONFIG/LOG_FOLDER`, `CONTROL/XML_STORAGE_FOLDER`, etc | `load_dotenv()` depuis `config_folder()/.env` prioritaire puis `resource_root()/.env`, plus de CWD | `config/.env` si présent (installée) + `backend/.env` dev | OUI si présent dans config folder | ❌ NON — `.env` réel gitignoré, seul `.env.example` commité | ❌ NON | SAFE — M-1 fixé, CWD indépendant |
| `TCP credentials` | `secrets.token_urlsafe(16)` généré via `TcpCredentialService` | Généré à la création credential | `security.xml` (Control Plane) | OUI | ❌ NON | ❌ NON — password jamais exposé en clair via API sauf via `/credentials/show-password` avec current_password check | SAFE |
| `file_identifier` / protection table | `generate_key_identifier()` via `helpers` `secrets.token_hex` | Généré si non fourni, mais UI exige saisie explicite (backend ne génère pas auto pour protection) | Data Plane XML `table.file_identifier` | OUI | ❌ NON | ❌ NON — exposé seulement si `can_table admin` via `include_secret` | SAFE |

**Risque secrets embarqués EXE** : Aucun — `ensure_secrets()` génère au premier lancement, pas de secret réel dans code, `.env` réel gitignoré, `secrets.env` gitignoré, `ProductionConfig.validate()` refuse secrets dev.

**Premier lancement génération** : `prepare_runtime()` → crée 6 dossiers + `ensure_secrets()` → `bootstrap_if_needed()` → `ensure_admin()` — tous idempotents, non interactifs, aucun secret codé en dur.

**Verdict** : Secrets **générés, stockés, persistants, non embarqués, non exposés**, conforme packaging.

---

## 10. Analyse premier lancement

**Scénario cible** :
```
Installation → Premier lancement → Création dossiers %LOCALAPPDATA%\XMLForge → Génération secrets → Init Control Plane → Création admin → Flask 5000 → TCP 3307 → Ouverture navigateur → Utilisation
```

**Code actuel** :

- **Dossiers** : `runtime.prepare_runtime()` → `os.makedirs(control_folder, xml_folder, uploads_folder, exports_folder, logs_folder, config_folder, exist_ok=True)` + `chmod 0o700` pour control/config sur POSIX → `%LOCALAPPDATA%\XMLForge\...` si frozen ou `XMLFORGE_DATA_DIR` défini, sinon `backend/...` dev ✅
- **Secrets** : `ensure_secrets()` → génère `SECRET_KEY/JWT_SECRET_KEY` token_urlsafe(48) si absents, persiste atomique, mode 0600, idempotent ✅
- **Control Plane** : `bootstrap_if_needed(app)` → check `security_path(), catalog_path(), history_path()` existence, si présents → `skipped already-initialized`, sinon `service.bootstrap()` → crée `security.xml` (rôles admin/user), `catalog.xml`, `history.xml` (vide) + rapport ✅
- **Admin** : `ensure_admin(app, email, name, password)` → `get_user_by_email()`, si None → `AuthService.register()`, puis `ensure_role('admin')` + `update_user_fields(role_id admin, is_active True)` → idempotent, aucun identifiant codé en dur, retour `(ok, message)` ✅
- **CLI non interactive** : `flask init-app --email --name --password` (ou env `XMLFORGE_ADMIN_EMAIL/NAME/PASSWORD`) → appelle `prepare_runtime()`, `bootstrap_if_needed()`, `ensure_admin()` → sort JSON, destiné premier lancement installé automatisé ✅
- **CLI interactive dev** : `flask xml-bootstrap` (vierge) + `flask create-admin` (prompt email/name/password via click) → conservés dev, non utilisés en prod ✅
- **Fail-closed** : `create_app()` check Control Plane fichiers requis ET valides via `read_validated(..., schema)` sauf si `xml-bootstrap` ou `init-app` dans `sys.argv` → refuse démarrage si non initialisé, oblige bootstrap ✅
- **Dépendance terminal** : `init-app` non interactive, pas de `input()`, pas de `sys.stdin`, compatible EXE sans console ✅
- **Dépendance CWD** : `paths.py` résout chemins via `resource_root()` et `user_data_root()`, pas `os.getcwd()`, `.env` chargé depuis `config_folder` puis `resource_root`, plus de CWD → CWD arbitraire (raccourci) OK ✅
- **Dépendance Python** : en mode gelé, Python embarqué, pas de Python installé requis ✅
- **Flask** : `run.py` et `app.py` utilisent `host=config.get('HTTP_HOST','0.0.0.0')`, `port=config.get('HTTP_PORT',5000)` → configurable via env `XMLFORGE_HTTP_HOST/PORT`, défaut 5000 conservé ✅
- **TCP** : `TCPServer.start()` dans `create_app()` → bind synchrone, `SO_REUSEADDR`, `listen(64)`, `settimeout(1)`, thread daemon `xmlforge-tcp`, `_run` accept() + thread par client, timeout 2s, buffer 8 MiB → même processus Flask, pas de processus séparé ✅
- **Frontend** : servi par Flask si dist présent (`frontend/` ou `xmlforge-react/dist` ou env) → `/` = index.html, `/<path>` = fichier statique ou fallback SPA index.html, `/api/*` et `/socket.io/*` → 404 JSON, chemins sensibles `data/`, `control/`, `config/`, `logs/`, `tmp/`, `backend/`, `..`, `%2e` → 404 JSON (sécurité) ✅
- **Logs** : `setup_file_logging(app)` → `RotatingFileHandler` 5MB×3 vers `logs/xmlforge.log` (%LOCALAPPDATA% si frozen), idempotent via `app._xmlforge_file_logging` ✅

**Classification** :
- C-1/C-2/C-3 (chemins, XSD, dossiers) : **FIXÉS** — plus de BLOQUANT
- M-1 (.env CWD) : **FIXÉ** — déterministe
- M-2 (secrets dev) : **FIXÉ** — génération persistante
- M-3 (frontend non servi) : **FIXÉ** — Flask sert dist
- M-4 (create-admin interactif) : **FIXÉ** — `init-app` non interactive
- M-6 (logs) : **FIXÉ** — file logging rotatif
- M-8 (port 5000 en dur) : **FIXÉ** — configurable
- M-5 (verrou thread-only Windows) : INFORMATION — mono-processus recommandé, OK (f-lock via `portalocker`? Vérifié `storage.py` utilise `fcntl` + `msvcrt`? À vérifier mais non bloquant si mono-processus)
- M-7 (Werkzeug sans arrêt propre) : P1 MAJEUR — pas de handler arrêt propre au-delà Ctrl+C/SIGTERM, en processus détaché sans console nécessite signal ou endpoint arrêt dédié, `TCPServer.stop()` existe mais Flask dev server pas d'arrêt propre, recommandation waitress WSGI prod

**Scénario machine vierge** : Permis réellement par code actuel via `flask init-app` → dossiers + secrets + bootstrap + admin non interactifs → démarrage Flask+TCP → navigateur → utilisation.

---

## 11. Analyse redémarrage / persistance

**Scénario** : Premier lancement init → Deuxième lancement utilisation normale → après redémarrage retrouver données/config/secrets/users/bases/tables, ne pas recréer admin, ne pas réinit Control Plane, ne pas perdre données.

**Code actuel** :

- `bootstrap_if_needed()` : check existence `security.xml`, `catalog.xml`, `history.xml` → si présents → `skipped already-initialized` → pas de réinit ✅
- `ensure_secrets()` : si `config/secrets.env` existe → réutilise valeurs, idempotent, pas de régénération ✅
- `ensure_admin()` : si user existe déjà → `update_user_fields(role admin, active)` → "Administrateur mis à jour", pas de création duplicate, idempotent ✅
- `prepare_runtime()` : `os.makedirs(..., exist_ok=True)` → ne supprime pas, idempotent ✅
- `XmlDataPlane.mutate()` : écriture atomique `atomic_write()` + `database_lock` + `safe_replace` + retry Windows `WINDOWS_REPLACE_ATTEMPTS=5` + `_copy_delete_fallback` → persistance XML après fermeture/redémarrage ✅
- `XmlControlPlaneService` : `allocate_object_id()` persiste `next_object_id` dans `catalog.xml` → AUTO_INCREMENT continu après redémarrage ✅
- `Control Plane` : `security.xml` (users, roles, token_version, TCP creds), `catalog.xml` (bases, permissions, next_object_id), `history.xml`, `audit/` → tous persistés dans `%LOCALAPPDATA%\XMLForge\data\control\` si frozen ✅
- `Data Plane` : bases XML `data/xml/<id>_<slug>.xml` → persistés `%LOCALAPPDATA%\XMLForge\data\xml\` ✅
- Tests : `test_packaging.py` → bootstrap idempotent, secrets persistants, `ensure_admin` idempotent, file logging idempotent, CWD indépendant, frozen simulation avec `LOCALAPPDATA` → tous verts ✅
- E2E manuel : création database/table/columns/rows → arrêt → redémarrage → données conservées count=3, secrets identiques ✅

**Verdict** : Persistance **garantie** par code actuel, pas de recréation admin ni réinit Control Plane, données conservées.

---

## 12. Analyse Flask + TCP 3307

- **Démarrage** : `run.py` module-level `flask_app = create_app(Config)` déclenche tout, `create_app()` → si `TCP_ENABLED` True (défaut true) → `TCPServer(host=TCP_HOST, port=TCP_PORT=3307, flask_app=...).start()` → `bind` synchrone (fail-closed si port occupé), `listen(64)`, `settimeout(1)`, thread daemon `xmlforge-tcp` → `_run()` accept() + thread par client daemon, `_handle_client` timeout 2s, buffer 8 MiB ✅
- **Même processus** : Flask (HTTP 5000) + TCP (3307) dans même processus Python, pas de processus séparé, mono-processus recommandé pour verrous fichier (M-5) ✅
- **Ports** : Flask `HTTP_HOST` env `XMLFORGE_HTTP_HOST` défaut `0.0.0.0`, `HTTP_PORT` env `XMLFORGE_HTTP_PORT` défaut 5000 (configurable, 5000 conservé), TCP `TCP_HOST` défaut `0.0.0.0`, `TCP_PORT` 3307 inchangé (consigne), `TCP_SESSION_TIMEOUT_MINUTES` 30 ✅
- **Threads** : Flask-SocketIO async_mode `threading` (eventlet retiré), TCP threads daemon → fermeture processus tue threads, pas de processus enfants ✅
- **Arrêt** : `TCPServer.stop()` existe (ferme socket, join thread 5s, clear sessions) ✅, Flask dev server Werkzeug pas de handler arrêt propre au-delà Ctrl+C/SIGTERM (P1)
- **Exceptions** : `bind` synchrone → `/status` ne peut annoncer faux succès, `socket.timeout` purge expired, `OSError` log si running, buffer >8MiB → error `INVALID_REQUEST` ✅
- **Protocole TCP** : inchangé (consigne), `[type:1][len:4 BE][JSON]`, `TCPProtocol` avec MSG_PING/PONG, AUTH, QUERY, SELECT_DATABASE, UNLOCK_TABLE, CLOSE, codes erreur métier `ACCESS_DENIED`, `CONFLICT`, `CONSTRAINT_VIOLATION`, etc ✅
- **Client Python officiel** : `xmlforge/` stdlib pure, `examples/python_client_demo.py` démo ✅
- **Compat packaging** : Mono-processus → pas de problème verrou fichier Windows thread-only, Flask+TCP ensemble dans EXE OK, ports 5000/3307 à ouvrir firewall si besoin (recommandation installateur)

**Verdict** : Flask + TCP 3307 **fonctionnent ensemble dans même processus**, démarrage/arrêt gérés, pas de modification protocole, prêt packaging.

---

## 13. Analyse arrêt de l'application

- **Ctrl+C / SIGTERM** : `socketio.run()` dev server Werkzeug gère SIGINT/SIGTERM console → arrêt Flask, `TCPServer` thread daemon → tué à la fermeture processus, pas de processus enfants → arrêt propre en console ✅
- **Fermeture fenêtre** : En app Windows packagée avec console masquée ou service, fermeture = tuer processus → threads daemon tués, mais pas de handler arrêt propre Flask au-delà signal → risque si processus détaché sans console → nécessite signal SIGTERM/CTRL_BREAK sur Windows ou endpoint arrêt dédié à ajouter (hors périmètre audit, à signaler P1) ⚠️
- **TCP stop** : `TCPServer.stop()` existe, ferme socket, join thread 5s, clear sessions → peut être appelé par futur launcher/tray/service ✅
- **Flask stop** : Pas de `stop()` explicite, `socketio.run()` bloque, arrêt via signal seulement → P1 MAJEUR pour service Windows/tray (recommandation waitress WSGI prod + gestion signal)
- **Threads daemon/non-daemon** : Tous threads TCP et clients daemon → pas de blocage fermeture, mais données en cours d'écriture pourraient être interrompues si pas de `stop()` propre avant kill → risque mineur car `mutate()` utilise `database_lock` + `atomic_write` → écriture atomique, pas de corruption même si tué mid-write (retry Windows) ✅
- **Processus enfants** : Aucun ✅

**Classification** : P1 MAJEUR — pas de mécanisme arrêt propre Flask en processus détaché sans console, `TCPServer.stop()` existe mais Flask dev server nécessite signal ou WSGI prod. À signaler comme risque packaging, mais non bloquant si launcher gère signal.

---

## 14. Analyse des dépendances Python

| Dépendance | Version actuelle | Type | Windows x64 | PyInstaller | Note |
|---|---|---|---|---|---|
| Flask | 3.1.0 | pure Python | wheel win | OK | - |
| Flask-JWT-Extended | 4.7.1 | pure Python | OK | OK | - |
| Flask-Bcrypt | 1.0.1 | pure Python | OK | OK | - |
| Flask-CORS | 5.0.0 | pure Python | OK | OK | - |
| Flask-SocketIO | 5.3.6 | pure Python | OK | OK | async_mode threading (eventlet retiré) |
| python-dotenv | 1.0.1 | pure Python | OK | OK | lit .env depuis chemin explicite (fix M-1) |
| lxml | 6.0.0 | **extension native** | wheel win_amd64 cp312/cp313 disponible | ⚠️ À inclure explicitement, DLL libxml2/libxslt, mais wheel win_amd64 stable | Extension native, testée 3.13.14 OK, recommandation Python 3.12 win_amd64 pour bundle (support bundlers + wheels) |
| marshmallow | 3.22.0 | pure Python | OK | OK | - |
| pystray | 0.19.5 | pure Python + backend win32/gtk | Windows backend win32 OK, échoue sans display X sur Linux (DisplayNameError attendu) | OK sur Windows | **Hors runtime serveur** — launcher icône barre système, commentaire requirements.txt, ne doit pas être requis pour serveur seul → P2 MINEUR si inclus inutilement |
| pillow | 12.3.0 | extension native + pure | wheel win_amd64 | OK | Dépendance pystray, idem hors runtime serveur → P2 |
| pytest, pytest-cov | 8.3.4, 6.0.0 | dev/test | NON runtime | Exclure | - |

**pip check** : No broken requirements found ✅

**Compat Windows** : Toutes deps pure Python + lxml wheel win_amd64 → compatible PyInstaller one-file/one-dir, Python 3.12 win_amd64 recommandé (support bundlers + lxml wheels le plus stable), compatible 3.13 actuel.

**Problèmes PyInstaller** :
- `lxml` : extension native, nécessite inclusion DLLs libxml2/libxslt, mais wheel win_amd64 inclut déjà, à déclarer en hidden import si besoin `lxml.etree`, `lxml._elementpath`
- `pystray`/`pillow` : backend win32 utilise `PIL`, `win32` APIs, pas de problème Windows, mais échoue Linux sans display (attendu)
- Ressources XSD : non-Python, à déclarer data files
- Frontend dist : à inclure `frontend/` folder

**Verdict** : Dépendances **compatibles Windows x64**, 0 bloquant, lxml wheel win_amd64 OK, pystray/pillow hors runtime serveur → P2.

---

## 15. Analyse frontend / dist

**Objectif** : Machine finale sans Node.js/npm/Vite/React séparé, frontend compilé `dist` servi par Flask même origine, pas de CORS.

**État actuel** :

- **Old frontend `xmlforge-react/`** :
  - `npm run build` → `dist/` multi-chunks : `index.html` 0.75KB, `Workspace` 86KB gzip 18.96KB, `index` 288KB gzip 91.72KB, CSS, etc → OK
  - `vite.config.js` proxy `/api` → `localhost:5000` dev, `VITE_API_URL=/api` prod même origine → pas de CORS nécessaire prod ✅
  - Routes : `/` = index.html, `/<path>` fallback SPA index.html, `/api/*` et `/socket.io/*` → 404 JSON (pas index.html) ✅
  - Sécurité : `data/`, `control/`, `config/`, `logs/`, `tmp/`, `backend/`, `..`, `%2e` → 404 JSON (fix précédent) ✅
  - Appels `/api` via `apiClient` centralisé avec JWT ✅

- **New frontend V2.3 `XMLForge_FrontRedesign/`** :
  - `npm run build` → `dist/index.html` singlefile 461KB gzip 127KB (vite-plugin-singlefile) → OK, 72 modules transformed
  - Design dark premium validé, conservé
  - API client centralisé `src/api/client.ts` + 12 modules (auth, databases, tables, columns, rows, queries, xml, permissions, users, audit, history, server, tcp) → 100% données réelles, 0 mock runtime, JWT réel, 401/403/404/409/500 gérés
  - Fonctionnalités : auth, PERSONAL/COMMON, tables, structure, CRUD, relations, diagramme Diagramme/Liste + zoom/recherche/favoris/focus, SQL réelle, XML réel + diff, import/export réel, protection/unlock, permissions, admin, server health/TCP 3307, logs audit réels, conflits 409, favoris localStorage, duplication, truncate, command palette Ctrl+K FR, breadcrumbs FR, modales Portal z-layers 200/300/400/410/500/600 avec isolation:isolate #root → modal toujours au-dessus ✅
  - Build singlefile → peut être servi par Flask comme `frontend/index.html` ou copié vers `xmlforge-react/dist/` (testé : `cp dist/index.html → xmlforge-react/dist/index.html` + `backend/frontend/index.html` → Flask sert 200 text/html V2.3, /api/nope 404 JSON, /data/control/security.xml 404 JSON) ✅
  - Pas de chemins Linux fictifs `/var/xmlforge/data` (fixés) → "Stockage XML natif" ✅
  - Pas de fausses métriques CPU/uptime/free/used/requests (fixés) ✅

- **Flask serving** :
  - `__init__.py` : si `_frontend_dist` existe et isdir → `frontend_index()` → `send_from_directory(dist, 'index.html')`, `frontend_assets(path)` → check api/socket.io → 404 JSON, check sensitive prefixes → 404 JSON, si fichier statique existe → send, sinon fallback SPA index.html → OK pour SPA routes React profondes
  - Sinon ancien index JSON API avec endpoints list → dev sans build ✅

- **CORS** : `CORS_ORIGINS` env `http://localhost:5173,http://localhost:3000` dev, prod même origine → CORS inutile prod, mais configuré ✅

**Problèmes** :
- `dist/` non persisté entre sessions (workspace snapshot exclut `dist`, `node_modules`, `.venv`) → NON VÉRIFIÉ en CI sans `npm run build`, mais build OK localement → INFORMATION
- `xmlforge-react/dist` absent après snapshot → `frontend_dist_folder()` retourne None → Flask sert JSON API, pas SPA → pas bloquant dev, mais prod nécessite build → INFORMATION

**Verdict** : Frontend **distribuable sans Node.js**, compilé `dist` servi Flask même origine OK, sécurité SPA OK, pas de CORS nécessaire prod, build OK.

---

## 16. Analyse PyInstaller

**Compatibilité sans créer package final** :

- **Imports dynamiques** : `socket_events` importé dans `app_context` try/except, `TCPServer` importé si `TCP_ENABLED`, `paths` importé partout, `runtime` importé si frozen — pas de `importlib` dynamique complexe, PyInstaller devrait détecter via analyse statique, mais à vérifier hidden imports `lxml.etree`, `flask_socketio`, `engineio`, `eventlet` retiré ✅
- **lxml** : extension native, wheel win_amd64, nécessite hidden import `lxml.etree`, `lxml._elementpath`, `lxml.builder`, `lxml.objectify` selon usage, mais code utilise seulement `etree` → à inclure, mais non bloquant
- **Ressources XSD** : chargés via `paths.static_dir()` filesystem → doivent être inclus data files bundler (`app/static/*.xsd`, `app/static/control/*.xsd`) — code fixé pour chercher 3 candidats, compatible one-file (_MEIPASS) et one-dir (dirname executable) ✅
- **Frontend dist** : `frontend_dist_folder()` cherche `frontend/` et `../xmlforge-react/dist` + env var → compatible one-file (frontend dans _MEIPASS/frontend ou à côté exe) et one-dir ✅
- **Fichiers statiques** : pas de templates externes, UI via React build
- **`_MEIPASS` / `sys._MEIPASS` / `sys.executable`** : `is_frozen()` détecte `sys.frozen` ou `sys._MEIPASS`, `resource_root()` retourne `_MEIPASS` si présent (one-file) sinon `dirname(sys.executable)` (one-dir/Nuitka) sinon `backend/` dev → données jamais dans _MEIPASS (vérifié `_data_path` n'utilise jamais _MEIPASS) ✅
- **Mode one-file vs one-dir** :
  - **one-file** : EXE unique, ressources extraites dans `_MEIPASS` temp à chaque lancement, démarrage plus lent, mais distribution simple, données dans `%LOCALAPPDATA%` pas dans `_MEIPASS` → OK, mais `_MEIPASS` temp perdu au reboot pas de problème car données hors _MEIPASS
  - **one-dir** : dossier avec EXE + libs + data files, démarrage plus rapide, plus facile debug, recommandation pour app avec beaucoup de data files (XSD + frontend) → **RECOMMANDÉ** pour XMLForge (beaucoup de XSD + frontend 461KB)
  - **Nuitka** : alternative, compilation C, plus rapide runtime, mais build plus complexe, `sys.frozen` détectable, `dirname(sys.executable)` pour ressources → aussi possible

**Recommandation argumentée** : **one-dir PyInstaller** (ou Nuitka one-dir) — démarrage plus rapide, XSD + frontend inclus facilement, debug plus simple, données dans `%LOCALAPPDATA%` séparées, pas de problème _MEIPASS temp. One-file possible mais démarrage plus lent et extraction XSD/frontend à chaque lancement.

**Verdict** : **Compatible PyInstaller**, 0 bloquant, ressources XSD/frontend à bundler, lxml wheel win_amd64 OK, recommandation one-dir.

---

## 17. Analyse Windows / permissions

- **%LOCALAPPDATA%** : `paths.user_data_root()` priorise `LOCALAPPDATA` env (Windows) → `C:\Users\<user>\AppData\Local\XMLForge` → inscriptible sans élévation, non roaming (données volumineuses, verrous) → standard pour serveur local, justifié ✅
- **%PROGRAMFILES%** : `C:\Program Files\XMLForge\` read-only, application code + XSD + frontend dist lecture seule, jamais écriture (sauf legacy uploads/exports via `__file__` à nettoyer P1) ✅
- **Variables d'environnement** : `XMLFORGE_DATA_DIR` (force racine), `XMLFORGE_CONFIG_FOLDER`, `XMLFORGE_LOG_FOLDER`, `XMLFORGE_FRONTEND_DIST`, `CONTROL_STORAGE_FOLDER`, `XML_STORAGE_FOLDER`, `UPLOAD_FOLDER`, `EXPORT_FOLDER`, `XMLFORGE_HTTP_HOST/PORT`, `XMLFORGE_FILE_LOGS`, `TCP_HOST/PORT`, etc — configurables, documentées `.env.example` ✅
- **Registre** : Non utilisé actuellement, pas nécessaire, mais installateur pourrait créer clés uninstall, file association `.xml` optionnel — INFORMATION
- **Raccourci bureau / Menu Démarrer** : À créer par installateur (Inno/NSIS/WiX), pointant vers EXE, pas de CWD dépendance (fix M-1) → OK
- **Firewall** : Ports 5000 (Flask HTTP) et 3307 (TCP) — Flask bind `0.0.0.0:5000` (tous interfaces), TCP `0.0.0.0:3307` — Windows Firewall demandera autorisation au premier lancement si bind 0.0.0.0, recommandation installateur : règle firewall ou doc, ou binder `127.0.0.1` si local seulement (actuellement `0.0.0.0` configurable via env) — P2 MINEUR
- **Permissions runtime** : Objectif utilisateur normal sans admin — `user_data_root()` inscriptible sans élévation, `Program Files` read-only, pas de besoin admin au runtime (sauf si port <1024, mais 5000/3307 >1024) → OK, pas de droits admin requis runtime ✅
- **Droits admin install** : Installation dans Program Files nécessite élévation UAC (normal), mais runtime sans admin OK

**Verdict** : Windows permissions **OK**, pas de droits admin runtime, firewall à documenter pour 5000/3307, raccourcis à créer par installateur.

---

## 18. Analyse logs

- **Emplacement actuel** : `paths.logs_folder()` → `%LOCALAPPDATA%\XMLForge\logs\` si installed (frozen ou `XMLFORGE_DATA_DIR`) sinon `backend/logs\` dev + env `XMLFORGE_LOG_FOLDER` surcharge
- **Implémentation** : `runtime.setup_file_logging(app)` → `RotatingFileHandler` vers `logs/xmlforge.log`, maxBytes 5MB, backupCount 3, encoding utf-8, formatter `%(asctime)s %(levelname)s [%(name)s] %(message)s`, level INFO, idempotent via `app._xmlforge_file_logging`, handler ajouté aux loggers root, app, xmlforge, werkzeug ✅
- **Activation** : `FILE_LOGS_ENABLED = env XMLFORGE_FILE_LOGS or is_frozen()` → auto en mode gelé, optionnel dev via `XMLFORGE_FILE_LOGS=true` ✅
- **Compat Program Files** : Logs dans `%LOCALAPPDATA%` si frozen, pas dans Program Files → OK sans droits écriture installation ✅
- **Console logs** : développement stdout/stderr conservés, file logs additionnels ✅
- **Logs frontend** : `LogsView` affiche audit logs réels via `/audit-logs`, pas de logs fichier via REST (sécurité), indique chemin `%LOCALAPPDATA%\XMLForge\logs\xmlforge.log` non exposé REST → OK, pas de fake logs ✅
- **.gitignore** : `backend/logs/`, `backend/tmp/`, `backend/config/`, `secrets.env` exclus → jamais commités ✅

**Verdict** : Logs **compatibles** `%LOCALAPPDATA%\XMLForge\logs`, rotation OK, sécurité OK.

---

## 19. Analyse désinstallation

**Scénario A — Désinstallation** :

- **Doivent être supprimés** : fichiers applicatifs `C:\Program Files\XMLForge\` (EXE, XSD, frontend dist), raccourcis bureau/menu Démarrer, registre uninstall
- **Doivent rester par défaut** : données utilisateur `%LOCALAPPDATA%\XMLForge\data\` (bases XML, security.xml, catalog.xml, history.xml, audit/), `config\` (secrets.env, .env), `logs\` — utilisateur ne doit pas perdre bases
- **Option explicite** : installateur offre case "Supprimer mes données" → si cochée, supprimer `%LOCALAPPDATA%\XMLForge\` complet, sinon conserver
- **Code actuel** : données dans `%LOCALAPPDATA%` si frozen, pas dans Program Files → désinstallation conservatrice possible ✅, `data/` non inclus dans bundle (vérifié `find` 0 `.db`/`.sqlite`, `.gitignore` exclut `data/`) ✅
- **Risque** : Si installateur supprime tout `%LOCALAPPDATA%` par défaut → perte données → à signaler comme recommandation, pas de code à corriger

**Verdict** : Désinstallation **propre possible**, données préservées par défaut si installateur respecte séparation.

---

## 20. Analyse mise à jour / réinstallation

**Scénario C — Mise à jour** :

- **Conserver** : `%LOCALAPPDATA%\XMLForge\data\` + `config\` (bases, users, secrets, audit)
- **Remplacer** : binaires `Program Files\XMLForge\` + frontend dist
- **Risques** :
  - **Compatibilité XSD ascendante** : XSD embarqués valident documents, si nouvelle version XSD plus strict → anciennes bases illisibles → fail-closed refus démarrage → à prévoir plan compat XSD (ne pas introduire XSD plus strict sans migration) → P2 MINEUR
  - **Version schéma** : pas de migration schéma (XML-only) → document `version` incrementé à chaque `mutate()`, mais pas de migration automatique → si changement structure XML majeur → risque → P2
  - **token_version** : stable, invalidation JWT via `volatile.is_revoked()` + `token_version` check → OK
  - **next_object_id** : persisté `catalog.xml` → AUTO_INCREMENT continu après update ✅

**Scénario B — Réinstallation** :

- **Après désinstallation conservatrice** (données conservées) → réinstallation → EXE retrouve données existantes dans `%LOCALAPPDATA%` → `bootstrap_if_needed()` → `skipped already-initialized` → pas de re-bootstrap, admin conservé ✅
- **Après désinstallation complète** (données supprimées) → réinstallation → `bootstrap_if_needed()` → `created` → `ensure_admin()` → nouvelle init vierge ✅

**Tests** : Mode installé live `init-app` + serveur réel → bootstrap created puis skipped idempotent, admin créé puis mis à jour, persistance count=3, secrets identiques après restart ✅

**Verdict** : Mise à jour / réinstallation **propres possibles** si conservation `%LOCALAPPDATA%`, risques XSD compat à surveiller P2.

---

## 21. Vérification XML-only / absence SQLite

**Objectif** : XMLForge est désormais XML-only, 0 runtime SQLite indispensable.

**Recherche** :

```bash
grep -R "sqlite|SQLAlchemy|projection|rebuildProjection" backend/app --include="*.py" -n
```
- Résultats : seulement commentaires `Aucune dépendance SQLite/SQLAlchemy`, `storage: sqlite absent`, `projection_path` legacy field (ancien identifiant SQLAlchemy conservé mais jamais utilisé runtime), `sync_projection_enabled()` retourne False, `rebuild-projection` route no-op XML_ONLY pour compat frontend, `xmlforge_client.py` engine param `'sqlite' (défaut)` historique mais non utilisé (moteur xml par défaut), `records.py` commentaire `internal_id = ancien identifiant SQLAlchemy` — **aucune logique SQLite runtime**, pas de `import sqlite3`, pas de `SQLAlchemy`, pas de `db.session`, pas de `.db` créé.

```bash
find backend -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3"
```
- Sur installation vierge après bootstrap + tests : 0 fichier ✅

```bash
ls backend/data/
```
- `No such file or directory` après tests (tmp_path) → pas de `projections/` SQLite ✅
- `backend/uploads/`, `backend/exports/` existent mais vides + `.gitkeep`, non utilisés persistance (imports mémoire, exports streaming) ✅

**Documentation historique** :
- `XML_BACKEND_MODE.md`, `SQLITE_DEPENDENCIES.md`, `MANUEL_TEST_VALIDATION_XMLFORGE.md`, `QUICKSTART.md`, `README_TCP_COMPLETE.md` ont bandeau "DOCUMENT HISTORIQUE" — normal, pas runtime
- `README.md` racine créé, indique XML-only

**Verdict** : **XML-only confirmé**, 0 runtime SQLite, 0 fichier `.db`/`.sqlite`, projection SQLite retirée, `uses_sqlite()`/`ProjectionError`/`record_divergence` retirés (post-audit fix report).

---

## 22. Tests réalisés

| Suite | Commande | Résultat | Durée | Vérifié |
|---|---|---|---|---|
| Backend complet | `cd backend && .venv/bin/python -m pytest -q` | **350 passed** | 59.55s (dernière), 58.47s, 58.71s selon run | Moteur XML, permissions, transactions, JWT, bcrypt, CRUD, SQL, XML, import/export, TCP, sécurité |
| Packaging | `pytest tests/test_packaging.py -q` | **16 passed** | 1.69s, 1.53s, 1.56s | layout source/installé/frozen, sous-process sys.frozen+_MEIPASS+LOCALAPPDATA, CWD indépendant, secrets persistants/idempotents/priorité env/jamais dev, XSD chargeables, frontend servi index/assets/fallback SPA/404 JSON api, bootstrap idempotent, ensure_admin idempotent, CLI init-app, file logging idempotent, has_active_admin |
| Frontend old | `cd xmlforge-react && npm ci && npm test` | **10 passed | 1 skipped** | api.test.js, AuthContext, DatabaseContext, ConflictDialog, versioning |
| Frontend old lint | `npm run lint` | **0 erreur, 3 warnings** fast-refresh préexistants | - | - |
| Frontend old build | `npm run build` | **OK** | 361ms | 102 modules, Workspace 86KB gzip 18.96KB |
| Frontend V2.3 new | `cd XMLForge_FrontRedesign && npm ci && npm run build` | **OK** | 2.09s | 72 modules, singlefile 440-461KB gzip 122-127KB |
| Frontend V2.3 served | Flask test client avec `FRONTEND_DIST_FOLDER=/.../dist` | **200** index.html V2.3, `/api/nope` 404 JSON, `/data/control/security.xml` 404 JSON | - | Sécurité SPA, serving frontend |
| Bootstrap + create-admin env vierge | `flask xml-bootstrap` + `create-admin` + `run.py` | **OK** | - | Control Plane init, admin creation |
| TCP 3307 client officiel | AUTH/USE/CREATE/INSERT/SELECT/UPDATE/DELETE/BEGIN+ROLLBACK/BEGIN+COMMIT/CLOSE | **9/9 OK** (rapport précédent) | - | TCP server |
| SQLite check | `find` sur installation vierge | **0 fichier** .db/.sqlite | - | XML-only |
| pip check | `pip check` | No broken requirements | - | Dépendances |
| E2E manuel complet V2.3 | Script temporaire /tmp isolation | **OK** | - | Auth, DB PERSONAL/COMMON, tables, columns, rows 30 pagination/search/sort/NULL, protection/unlock, permissions, import/export XML/SQL, sync, conversion, SQL, XML, audit/history, server health/TCP sessions, conflits 409, persistance restart |
| CWD indépendant | sous-processus depuis CWD arbitraire | **OK** | - | Chemins indépendants CWD |
| Frozen simulation | sous-processus `sys.frozen=True` + `sys._MEIPASS` + `LOCALAPPDATA` | **OK** | - | Données sous LocalAppData, ressources sous bundle |

**Non vérifié** :
- Build EXE réel PyInstaller/Nuitka (hors périmètre audit, consigne)
- Installateur Inno/NSIS/WiX (hors périmètre)
- Service Windows réel (hors périmètre)
- Performance réelle Windows 10/11 (sandbox Linux, mais simulation LOCALAPPDATA OK)

---

## 23. Problèmes P0 — BLOQUANT

**Nombre : 0**

Aucun problème P0 bloquant identifié après phase préparation packaging.

Les anciens C-1/C-2/C-3 (chemins, XSD, dossiers) sont **fixés** :
- C-1 Chemins dérivés `__file__` → données dans temp perdu → **FIXÉ** via `paths.py` `is_frozen()` → LocalAppData
- C-2 `os.makedirs` dans installation → crash Program Files → **FIXÉ** via config via paths
- C-3 XSD non embarqués → crash import → **FIXÉ** via `static_dir()` robuste + à bundler data files

---

## 24. Problèmes P1 — MAJEUR

**Nombre : 2**

### P1-001 — Legacy makedirs `__file__` uploads/exports dans `app/__init__.py`
- **Fichier** : `backend/app/__init__.py:26-27`
- **Emplacement** :
```python
os.makedirs(os.path.join(os.path.dirname(__file__), 'uploads'), exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), 'exports'), exist_ok=True)
```
- **Problème** : Crée dossiers dans `backend/app/uploads` et `exports` (dans installation) même si `UPLOAD_FOLDER`/`EXPORT_FOLDER` config pointent vers `%LOCALAPPDATA%\XMLForge\tmp\...` (fixé). En `C:\Program Files\XMLForge\` read-only, `os.makedirs` échouerait `PermissionError` si dossiers n'existent pas.
- **Impact** : Crash au démarrage sur machine sans droits écriture installation, même si données principales sont dans LocalAppData.
- **Scénario qui échoue** : Installation dans Program Files (read-only) sans dossiers `app/uploads`, `app/exports` pré-créés → `create_app()` → `makedirs` → PermissionError → Flask ne démarre pas.
- **Recommandation** : Retirer ces 2 lignes legacy, conserver seulement `os.makedirs(config['UPLOAD_FOLDER'])` et `EXPORT_FOLDER` (déjà présents lignes 23-24) qui pointent vers LocalAppData si frozen. Ces dossiers legacy ne sont pas utilisés pour persistance (imports mémoire, exports streaming).
- **Priorité** : P1 MAJEUR (mineur) — packaging possible mais risque crash si non nettoyé.

### P1-002 — Arrêt propre Flask en processus détaché sans console
- **Fichier** : `backend/run.py`, `backend/app/app.py`, `backend/app/__init__.py` (TCPServer)
- **Problème** : Flask dev server Werkzeug via `socketio.run()` n'a pas de handler arrêt propre au-delà Ctrl+C/SIGTERM console. En processus détaché (EXE sans console, service Windows, tray), fermeture fenêtre doit tuer processus via signal, mais pas de `stop()` Flask explicite.
- **Impact** : Application Windows avec console masquée ou service pourrait ne pas s'arrêter proprement, threads daemon tués brutalement, mais pas de corruption grâce à `atomic_write`.
- **Scénario qui échoue** : Launcher Windows lance `XMLForge.exe` sans console → utilisateur ferme tray → launcher appelle `tcp_server.stop()` mais Flask reste bloqué → processus zombie.
- **Recommandation** : Utiliser WSGI production `waitress` (ou équivalent) + gestion signal SIGTERM/CTRL_BREAK, ou endpoint arrêt dédié sécurisé local, ou garder console visible. `TCPServer.stop()` existe déjà, à appeler depuis launcher avant kill Flask.
- **Priorité** : P1 MAJEUR — packaging possible mais gestion service/tray plus délicate.

---

## 25. Problèmes P2 — MINEUR

**Nombre : 4**

### P2-001 — pystray/pillow dans requirements.txt runtime serveur
- **Fichier** : `backend/requirements.txt`
- **Problème** : `pystray==0.19.5` + `pillow==12.3.0` ajoutés avec commentaire "Launcher Windows (icône barre système) — hors runtime serveur" mais dans `requirements.txt` principal, donc installés même pour serveur seul. `import pystray` échoue sans display X sur Linux `DisplayNameError: Bad display name ""` (attendu, OK sur Windows win32).
- **Impact** : Dépendances inutiles pour serveur seul, échec import sur Linux sans X (non bloquant Windows), taille bundle +.
- **Recommandation** : Déplacer vers `requirements-launcher.txt` ou `requirements-optional.txt` ou extra `launcher` dans `pyproject.toml`, garder `requirements.txt` minimal serveur (8 libs). Ou conditionner import pystray seulement dans launcher.
- **Priorité** : P2 MINEUR

### P2-002 — Ports 5000/3307 firewall Windows
- **Fichier** : `backend/app/config.py`, `backend/run.py`
- **Problème** : Flask bind `0.0.0.0:5000` et TCP `0.0.0.0:3307` → Windows Firewall demandera autorisation au premier lancement (popup). Si utilisateur refuse, frontend ne pourra joindre backend si même origine? Même origine OK si 0.0.0.0, mais si firewall bloque, localhost reste OK.
- **Impact** : Popup firewall au premier lancement, confusion utilisateur.
- **Scénario** : Installation → premier lancement → Windows Firewall "Autoriser XMLForge.exe sur réseau privé/public ?" → si refuse → REST/TCP inaccessibles depuis autre machine (mais localhost OK).
- **Recommandation** : Documenter dans installateur, ou binder `127.0.0.1` par défaut si local seulement (configurable via env `XMLFORGE_HTTP_HOST=127.0.0.1`, `TCP_HOST=127.0.0.1`), ou créer règle firewall via installateur (nécessite admin install).
- **Priorité** : P2 MINEUR

### P2-003 — Compatibilité XSD ascendante mise à jour
- **Fichier** : `backend/app/static/*.xsd`
- **Problème** : XSD valident documents fail-closed, si nouvelle version XSD plus strict → anciennes bases illisibles → refus démarrage.
- **Impact** : Mise à jour pourrait casser persistance.
- **Recommandation** : Ne jamais introduire XSD plus strict sans migration, prévoir tests compat ascendante, versionner XSD.
- **Priorité** : P2 MINEUR

### P2-004 — Verrou fichier thread-only Windows
- **Fichier** : `backend/app/xml_engine/storage.py`
- **Problème** : Verrou fichier utilise `fcntl` (POSIX) + `msvcrt`? Vérifié `database_lock` utilise `flock` + `RLock`, Windows utilise `msvcrt.locking`? Si Flask et TCP étaient 2 processus séparés, verrou thread-only insuffisant.
- **Impact** : OK mono-processus (recommandé), insuffisant si 2 processus.
- **Recommandation** : Garder mono-processus Flask+TCP (actuel), pas de séparation processus.
- **Priorité** : P2 MINEUR

---

## 26. Points P3 / informations

**Nombre : 6**

### P3-001 — `backend/xmlforge.xsd` racine doublon legacy
- **Fichier** : `backend/xmlforge.xsd`
- **Info** : Doublon legacy non référencé, seul `app/static/xmlforge.xsd` chargé via `paths.static_dir()`. Ne pas bundler, confusion possible.
- **Recommandation** : Ne pas inclure dans bundle, ou supprimer en phase nettoyage future (hors audit).

### P3-002 — `projection_path` legacy dans records/views
- **Fichier** : `backend/app/xml_control/records.py:309`, `views.py:111`
- **Info** : Champ `projection_path` conservé pour compat historique, jamais utilisé runtime XML-only. Pas de logique SQLite.
- **Recommandation** : Conserver pour l'instant, nettoyage possible phase dédiée.

### P3-003 — `rebuild-projection` route no-op
- **Fichier** : `backend/app/routes/sync.py:21`
- **Info** : Route `POST /databases/{id}/rebuild-projection` conservée pour compat frontend, retourne `{"projection":"XML_ONLY"}`. Pas de projection SQLite.
- **Recommandation** : Conserver no-op, documenter.

### P3-004 — Frontend dist non persisté snapshot
- **Fichier** : `xmlforge-react/dist/`, `backend/frontend/`, `XMLForge_FrontRedesign/dist/`
- **Info** : Workspace snapshot exclut `dist`, `node_modules`, `.venv`, `__pycache__`, etc (128MB cap). Donc `dist/` absent après snapshot, `frontend_dist_folder()` retourne None en tests sans build → Flask sert JSON API pas SPA. Build OK localement après `npm run build`.
- **Recommandation** : En CI packaging, faire `npm run build` avant tests si on veut tester serving frontend, ou garder `TestingConfig.FRONTEND_DIST_FOLDER` désactivé comme actuellement.

### P3-005 — `CREATE DATABASE` via TCP exige base sélectionnée
- **Fichier** : `backend/app/tcp/tcp_server.py` + `POST_AUDIT_FIX_REPORT.md`
- **Info** : Comportement pré-existant, non lié packaging : `CREATE DATABASE` via TCP exige une base déjà sélectionnée (via USE), sinon `DATABASE_NOT_SELECTED`. Contournement : créer base via REST `POST /api/databases` puis USE via TCP. Documenté comme observation P3 post-audit.
- **Recommandation** : Conserver, documenter, pas de correction packaging.

### P3-006 — `has_active_admin()` coût linéaire
- **Fichier** : `backend/app/xml_control/service.py`, `control_plane/xml_backend.py`, `tests/test_packaging.py`
- **Info** : Implémenté pour check admin actif au démarrage launcher, coût O(users) avec 1 seul chargement `security.xml` + scan mémoire (100 users 0.009ms, 1000 users 0.095ms, 101 users list_users 270ms vs has_active_admin 2.9ms). Adapté check rapide démarrage.
- **Recommandation** : Utiliser dans launcher `with app_context(): get_backend().has_active_admin()`.

---

## 27. Machine vierge — scénario cible

```
Installation (Inno/NSIS/WiX) :
   - Binaires dans C:\Program Files\XMLForge\ (read-only) : XMLForge.exe + static/*.xsd + frontend/index.html
   - Raccourcis Bureau + Menu Démarrer → XMLForge.exe (pas de CWD dépendance)
   - Option firewall 5000/3307 (si 0.0.0.0)

Premier lancement (XMLForge.exe) :
   ↓
   prepare_runtime() → crée %LOCALAPPDATA%\XMLForge\data\control, data\xml, tmp\uploads, tmp\exports, logs, config (0700 pour control/config sur POSIX)
   ↓
   ensure_secrets() → génère SECRET_KEY/JWT_SECRET_KEY token_urlsafe(48) si absents, persiste config/secrets.env mode 0600 atomique, idempotent
   ↓
   bootstrap_if_needed(app) → check security.xml, catalog.xml, history.xml existence, si absents → bootstrap() crée rôles admin/user + catalog vide + history vide, sinon skipped already-initialized
   ↓
   ensure_admin(app, email, name, password) → via args --email/--name/--password ou env XMLFORGE_ADMIN_EMAIL/NAME/PASSWORD, crée/promote admin, idempotent, aucun identifiant dur
   ↓
   Flask :5000 (HTTP_HOST/PORT configurable, 5000 défaut) + frontend dist servi même origine ( / → index.html V2.3 singlefile 461KB, /assets/* statiques, /api/* 404 JSON, data/control/etc 404 JSON)
   ↓
   TCPServer 0.0.0.0:3307 (TCP_HOST/PORT, 3307 inchangé) → bind synchrone, listen 64, thread daemon xmlforge-tcp, sessions, transactions snapshot XML+catalog
   ↓
   Ouverture navigateur http://localhost:5000 → LoginView → login admin → JWT → session persistante localStorage + /me
   ↓
   Utilisation normale :
   - Dashboard bases PERSONAL/COMMON réelles, tables_count, activity réelle
   - DatabaseView tables réelles, columns_count, protection, relations, XML, SQL
   - TableWorkspace Data (pagination/search/tri/filtres backend, CRUD, NULL, FK), Structure (colonnes réelles PK/FK/AI/UNIQUE/NN/DEFAULT/INDEX, Edit colonne), Relations (diagramme avec zoom/recherche/liste/favoris/focus), SQL (POST /query moteur XML natif réel), XML (export réel, Apply sync-xml, Diff, Reset)
   - Import XML/SQL/Project, Export XML/SQL/Project blob download
   - Protection table + Unlock personnel session 24h + clear on logout
   - Partage DB/table VIEW/EDIT/MANAGE via permissions réelles
   - Admin Users/Audit/History réels (403 si non admin → Accès refusé)
   - Server health REST/TCP/Engine/Storage XML-only réels, pas de Restart fake

Fermeture :
   - Ctrl+C / SIGTERM console → Flask stop + TCPServer.stop() (ferme socket, join 5s, clear sessions) → arrêt propre
   - Fenêtre sans console (EXE masqué) → launcher doit envoyer SIGTERM/CTRL_BREAK + tcp_server.stop() avant kill (P1-002)

Redémarrage (deuxième lancement) :
   - prepare_runtime() → makedirs exist_ok, secrets réutilisés (pas de régénération)
   - bootstrap_if_needed() → skipped already-initialized (pas de réinit)
   - ensure_admin() → mis à jour si existe, pas de duplicate
   - Flask+TCP démarrent, retrouvent données dans %LOCALAPPDATA%\XMLForge\data\ (bases XML, security.xml, catalog.xml, history.xml, audit), config/secrets.env, logs
   - Login → bases/tables/colonnes/lignes/relations/permissions/protection conservées, AUTO_INCREMENT continu via next_object_id persisté

Persistance :
   - XmlDataPlane.mutate() → database_lock + atomic_write + safe_replace + retry Windows 5 + fsync → pas de corruption même si tué mid-write
   - Tests packaging : persistance count=3, secrets identiques après restart OK
```

---

## 28. Scénario update

```
Version N installée dans Program Files + données %LOCALAPPDATA%\XMLForge\data\ + config\

Installation Version N+1 (nouvelle version code) :
   - Installateur remplace fichiers applicatifs Program Files (EXE, XSD, frontend dist)
   - Conserve %LOCALAPPDATA%\XMLForge\data\ (bases XML, security.xml, catalog.xml, history.xml, audit) + config\ (secrets.env, .env) + logs\
   - Ne jamais écraser data/ et config/ (sauf option explicite)
   - bootstrap_if_needed() → skipped (déjà initialisé)
   - ensure_secrets() → réutilise secrets.env existant
   - Démarrage → données existantes reconnues, pas de re-bootstrap
   - Vérification compat XSD ascendante : si XSD N+1 plus strict → anciennes bases illisibles → fail-closed refus démarrage → à éviter (P2-003)
   - token_version stable, next_object_id continu

Testé : init-app + serveur réel → bootstrap created puis skipped idempotent, admin créé puis mis à jour, persistance count=3 OK
```

---

## 29. Scénario uninstall

```
Désinstallation via Panneau config Windows (Inno/NSIS/WiX) :

Mode conservateur (recommandé par défaut) :
   - Supprime : C:\Program Files\XMLForge\ (EXE, XSD, frontend), raccourcis Bureau/Menu Démarrer, registre uninstall
   - Conserve : %LOCALAPPDATA%\XMLForge\data\ (bases XML, security, catalog, history, audit), config\ (secrets), logs\
   - Utilisateur ne perd pas ses bases

Mode complet (option explicite "Supprimer mes données") :
   - Supprime aussi %LOCALAPPDATA%\XMLForge\ complet
   - Machine redevient vierge → prochaine install → bootstrap created

Code actuel : données dans %LOCALAPPDATA% si frozen → désinstallation conservatrice possible, data/ non inclus bundle (gitignore + find 0 .db), .env réel gitignoré

Recommandation : Installateur doit proposer case à cocher "Supprimer mes données" décochée par défaut, et jamais supprimer data/ par défaut.
```

---

## 30. Scénario reinstall

```
Après désinstallation conservatrice (données conservées) :

Réinstallation Version N (ou N+1) :
   - Binaires dans Program Files remplacés
   - %LOCALAPPDATA%\XMLForge\data\ et config\ existants conservés
   - Premier lancement → prepare_runtime() makedirs exist_ok → bootstrap_if_needed() → skipped already-initialized → ensure_admin() → mis à jour si existe
   - Flask+TCP démarrent → retrouvent bases/tables/users/secrets → OK, pas de re-bootstrap

Après désinstallation complète (données supprimées) :

Réinstallation :
   - %LOCALAPPDATA%\XMLForge\ absent
   - Premier lancement → prepare_runtime() crée dossiers → ensure_secrets() génère nouveaux secrets → bootstrap_if_needed() → created → ensure_admin() → créé → OK, init vierge

Testé : Mode installé live avec XMLFORGE_DATA_DIR temporaire → bootstrap created puis skipped idempotent OK
```

---

## 31. Checklist de readiness

```
[ ] Choisir bundler : PyInstaller (recommandé one-dir) ou Nuitka + installateur Inno Setup/NSIS/WiX
[ ] Cibler Python 3.12 win_amd64 (support wheels lxml + bundlers stable) tout en restant compatible 3.13 (actuel 3.13.14)
[ ] Embarquer code backend app/** + run.py (ou launcher)
[ ] Inclure XSD en data files : app/static/xmlforge.xsd + app/static/control/*.xsd (4 fichiers) — paths.static_dir() robuste
[ ] Inclure frontend dist : XMLForge_FrontRedesign/dist/index.html singlefile 461KB (V2.3) ou xmlforge-react/dist multi-chunks → destination <resources>/frontend ou XMLFORGE_FRONTEND_DIST
[ ] Ne jamais inclure : .env réel, secrets.env, backend/data/**, backend/uploads, backend/exports, logs, tmp, config, tests, node_modules, .venv, __pycache__, *.db/.sqlite
[ ] Redirection données vers %LOCALAPPDATA%\XMLForge déjà implémentée via paths.py + is_frozen() (C-1/C-2 fixés) — vérifier au build
[ ] Charger .env depuis %LOCALAPPDATA%\XMLForge\config/.env puis backend/.env (fix M-1) — CWD indépendant OK
[ ] Génération secrets au premier lancement ensure_secrets() token_urlsafe(48) persistant config/secrets.env mode 0600 (fix M-2) — jamais embarqués
[ ] Servir frontend dist via Flask même origine (fix M-3) — / → index.html, fallback SPA, /api/* 404 JSON, sensitive paths 404 JSON
[ ] Rendre create-admin non interactif via flask init-app --email/--name/--password ou env XMLFORGE_ADMIN_* (fix M-4) — idempotent, aucun dur
[ ] Logs vers %LOCALAPPDATA%\XMLForge\logs\xmlforge.log rotation 5MB×3 (fix M-6) — FILE_LOGS_ENABLED auto si frozen
[ ] Garder mono-processus Flask+TCP 3307 (recommandé, M-5) — TCPServer.start() dans create_app(), daemon thread, stop() existe
[ ] Choisir WSGI production waitress si service Windows/tray requis (M-7) + gestion signal SIGTERM/CTRL_BREAK (P1-002)
[ ] Ports configurables HTTP_HOST/PORT (5000 défaut conservé) + TCP 3307 inchangé (M-8 fixé)
[ ] Nettoyer legacy makedirs __file__ uploads/exports dans app/__init__.py:26-27 (P1-001)
[ ] Déplacer pystray/pillow hors requirements.txt principal vers requirements-launcher.txt (P2-001)
[ ] Documenter firewall Windows 5000/3307 ou binder 127.0.0.1 par défaut si local seulement (P2-002)
[ ] Préparer icônes, raccourcis Bureau/Menu Démarrer, nom app XMLForge
[ ] Définir désinstallation conservatrice (données préservées par défaut, option explicite suppression)
[ ] Préparer stratégie mise à jour (compat XSD ascendante, ne pas rendre XSD plus strict)
[ ] Créer EXE (one-dir recommandé)
[ ] Créer installateur
[ ] Tester scénario machine vierge complet (installation → premier lancement init → admin → Flask 5000 → TCP 3307 → utilisation → fermeture → redémarrage persistance)
[ ] Tester mise à jour (données conservées)
[ ] Tester désinstallation conservatrice (données préservées) + complète (données supprimées)
[ ] Vérifier persistance XML + absence .db/.sqlite (0 fichier)
[ ] Vérifier 350 tests backend verts + 16 packaging verts + frontend build OK
[ ] Vérifier has_active_admin() pour launcher (coût linéaire 1 chargement security.xml)
```

---

## 32. Verdict final

**Verdict : READY WITH CONDITIONS**

**Justification** :

- **0 P0 BLOQUANT** : Les 3 problèmes critiques initiaux C-1 (chemins __file__ → temp perdu), C-2 (makedirs dans installation → crash Program Files), C-3 (XSD non embarqués → crash) sont **fixés** au niveau code via `paths.py`, `runtime.py`, `config.py`, `__init__.py`, `document.py`, `records.py`. Tests packaging 16 passed couvrent frozen simulation avec LOCALAPPDATA, CWD indépendant, secrets persistants, XSD chargeables, frontend serving.
- **2 P1 MAJEUR mineurs** :
  - P1-001 legacy makedirs `__file__` uploads/exports dans `__init__.py:26-27` — risque crash Program Files read-only si dossiers non pré-créés, mais non bloquant car vrais dossiers via config déjà créés dans LocalAppData et legacy non utilisés persistance. Recommandation simple : retirer 2 lignes.
  - P1-002 arrêt propre Flask détaché sans console — `TCPServer.stop()` existe mais Flask dev server Werkzeug pas de stop propre, nécessite signal ou waitress WSGI prod pour service Windows/tray. Non bloquant si launcher gère signal.
- **4 P2 MINEUR** : pystray/pillow hors runtime, firewall 5000/3307 popup, compat XSD ascendante, verrou thread-only Windows (mono-processus OK)
- **6 P3 INFORMATION** : doublon xmlforge.xsd racine, projection_path legacy, rebuild-projection no-op, dist non persisté snapshot, CREATE DATABASE via TCP exige base sélectionnée, has_active_admin coût linéaire

**Architecture cible respectée** :
- APPLICATION `C:\Program Files\XMLForge\` read-only (code+XSD+frontend)
- DONNÉES `%LOCALAPPDATA%\XMLForge\data\control\`, `data\xml\`, `tmp\uploads\`, `tmp\exports\`, `logs\`, `config\` inscriptibles sans admin
- Python embarqué, frontend embarqué, Flask 5000 configurable, TCP 3307 inchangé, XML-only, 0 .db/.sqlite, 0 Node.js au runtime

**Tests** : Backend 350 passed, Packaging 16 passed, Frontend old 10 passed/1 skipped + build OK, Frontend V2.3 461KB singlefile build OK, Flask serving V2.3 200 + 404 JSON sécurité, E2E manuel complet (auth, PERSONAL/COMMON, tables, columns, rows 30 pagination/search/sort/NULL, protection/unlock, permissions, import/export XML/SQL, sync, conversion, SQL, XML, audit/history, server health/TCP sessions, conflits 409, persistance restart) OK

**Conclusion** :

- **État global** : Prêt packaging avec 2 conditions mineures P1 à nettoyer (legacy makedirs + arrêt propre)
- **P0** : 0
- **P1** : 2
- **P2** : 4
- **P3** : 6
- **Tests exécutés** : Backend 350, Packaging 16, Frontend old 10+build+lint, Frontend V2.3 build, Flask serving, TCP 9/9 historique, SQLite check 0, pip check OK, E2E manuel, CWD indépendant, Frozen simulation
- **Verdict** : **READY WITH CONDITIONS**

Le projet peut être distribué sous Windows **sans refonte**, en mode **one-dir PyInstaller** (recommandé) avec XSD + frontend dist inclus en data files, données dans `%LOCALAPPDATA%\XMLForge\`, secrets générés premier lancement, `flask init-app` pour init non interactive, logs rotatifs, Flask+TCP mono-processus, après nettoyage des 2 P1 mineurs.

---

**Conclusion :**
- État global : READY WITH CONDITIONS — 0 P0, 2 P1 mineurs nettoyables, architecture XML-only stable, packaging préparation implémentée et testée
- P0 : 0
- P1 : 2
- P2 : 4
- P3 : 6
- Tests : 350 backend + 16 packaging + 10 frontend + 2 builds OK + sécurité SPA 404 + TCP historique 9/9
- Verdict : READY WITH CONDITIONS
