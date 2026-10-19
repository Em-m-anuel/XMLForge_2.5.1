# PACKAGING_PREPARATION_REPORT.md

**Objet :** préparation technique de XMLForge au packaging Windows (EXE + installateur)
**Date :** 2026-09-12
**Référence :** `PACKAGING_READINESS_AUDIT.md` (problèmes C-1, C-2, C-3, M-1…M-8)

---

## 1. Résumé

Le code a été adapté pour permettre un packaging Windows propre, **sans créer
d'EXE ni d'installateur**, et **sans modifier l'architecture** (moteur XML,
protocole TCP 3307, permissions, transactions, REST, client Python inchangés).

Réalisé :
- **Séparation ressources applicatives / données runtime** : en mode gelé (EXE),
  les données vont sous `%LOCALAPPDATA%\XMLForge\` (data/, tmp/, logs/, config/),
  jamais dans le dossier d'installation ni dans `_MEIPASS` (C-1/C-2).
- **Chargement XSD robuste** en mode source et gelé (C-3).
- **Configuration `.env` déterministe**, indépendante du CWD (M-1).
- **Secrets persistants générés au premier lancement**, jamais en dur, jamais
  dans Git (M-2).
- **Frontend `dist` servi par Flask** en production (même origine, un seul
  processus) (M-3).
- **Initialisation non interactive** : commande `flask init-app` (dossiers +
  secrets + bootstrap + admin) (M-4).
- **Logs fichier** rotatifs (actifs en mode gelé, optionnels en dev) (M-6).
- **Ports configurables** : HTTP `5000` (défaut conservé), TCP `3307` inchangé (M-8).

Aucun bundler ni installateur n'a été installé ou exécuté. Aucun commit Git
automatique n'a été effectué (consigne respectée).

---

## 2. Modifications

| Fichier | Problème | Solution | Justification |
|---|---|---|---|
| `backend/app/paths.py` (**nouveau**) | C-1/C-2/C-3 | Module unique de résolution des chemins : `resource_root()` (appli), `user_data_root()` (`%LOCALAPPDATA%\XMLForge`), `control_folder()`, `xml_folder()`, `uploads_folder()`, `exports_folder()`, `logs_folder()`, `config_folder()`, `static_dir()`, `frontend_dist_folder()` ; détection `is_frozen()` via `sys.frozen`/`sys._MEIPASS` | séparer les données (écritures) des ressources (lecture seule) |
| `backend/app/runtime.py` (**nouveau**) | M-2/M-4/M-6 | `prepare_runtime()`, `ensure_secrets()` (génération/persistance idempotente, 0600), `bootstrap_if_needed()`, `ensure_admin()` (idempotent, aucun identifiant codé en dur), `setup_file_logging()` | API réutilisable par le futur launcher ; non appelée en dev |
| `backend/app/config.py` | C-1/C-2/M-1/M-2/M-8 | dossiers de données via `paths` ; chargement `.env` depuis `config/.env` puis `backend/.env` (plus de CWD) ; `ensure_secrets()` en mode gelé uniquement ; `HTTP_HOST`/`HTTP_PORT` (défaut 5000) ; `LOG_FOLDER`/`CONFIG_FOLDER`/`FILE_LOGS_ENABLED`/`FRONTEND_DIST_FOLDER` | configuration déterministe et sans secrets en dur |
| `backend/app/__init__.py` | M-3/M-4/M-6 | service du frontend `dist` (index + assets + fallback SPA ; `/api*` et `/socket.io*` restent des 404 JSON) ; commande `flask init-app` ; logs fichier si `FILE_LOGS_ENABLED` ; skip du contrôle fail-closed pour `init-app` | un seul processus sert l'UI et l'API |
| `backend/app/xml_engine/document.py` | C-3 | XSD `xmlforge.xsd` chargé via `paths.static_dir()` | robuste en mode gelé |
| `backend/app/xml_control/records.py` | C-3 | XSD du Control Plane via `paths.static_dir()/control` | robuste en mode gelé |
| `backend/run.py`, `backend/app/app.py` | M-8 | `host`/`port` lus depuis la config (`HTTP_HOST`/`HTTP_PORT`) | 5000 conservé, configurable |
| `.gitignore` | M-2 (sécurité) | ajout `backend/logs/`, `backend/tmp/`, `backend/config/`, `secrets.env` | les données/secrets générés ne sont jamais commités |
| `backend/.env.example` | documentation | documente `XMLFORGE_HTTP_HOST/PORT`, `XMLFORGE_DATA_DIR`, `XMLFORGE_FILE_LOGS`, `XMLFORGE_FRONTEND_DIST`, `XMLFORGE_CONFIG/LOG_FOLDER` + flux `init-app` | prépare la config installée |
| `backend/tests/test_packaging.py` (**nouveau**) | validation | 15 tests (chemins, secrets, XSD, frontend, init, CWD, frozen, logs) | régression packaging couverte |

**Fichiers supprimés :** aucun.

---

## 3. Runtime paths

Layout « installé » (mode gelé, ou `XMLFORGE_DATA_DIR` défini) :

```text
%LOCALAPPDATA%\XMLForge\          (ou $XDG_DATA_HOME/XMLForge ; XMLFORGE_DATA_DIR surcharge)
├── data\
│   ├── control\   security.xml · catalog.xml · history.xml · audit\YYYY-MM.xml[.gz] (+ .lock)
│   └── xml\       bases XML utilisateurs (<id>_<slug>.xml)
├── tmp\
│   ├── uploads\   fichiers temporaires / imports
│   └── exports\   exports temporaires
├── logs\          xmlforge.log (rotation 5 Mio × 3)
└── config\        .env + secrets.env (SECRET_KEY / JWT_SECRET_KEY, mode 0600)
```

Mode développement (source) : comportement historique conservé
(`backend/data/control`, `backend/data/xml`, `backend/uploads`, `backend/exports`).
Les surcharges `CONTROL_STORAGE_FOLDER` / `XML_STORAGE_FOLDER` restent prioritaires.

---

## 4. Application resources (à inclure dans le futur bundle)

| Ressource | Source | Destination attendue dans le bundle |
|---|---|---|
| Code Python `backend/app/**` | sources | compilé/gelé par le bundler |
| `app/static/xmlforge.xsd` | `backend/app/static/xmlforge.xsd` | `static/xmlforge.xsd` (layout `app/static` préservé **ou** racine) |
| `app/static/control/*.xsd` (4) | `backend/app/static/control/` | idem (`static/control/*.xsd`) |
| Frontend buildé `dist/` | `xmlforge-react/dist/` (après `npm run build`) | `frontend/` à la racine du bundle (ou `XMLFORGE_FRONTEND_DIST`) |

`paths.static_dir()` cherche dans l'ordre : `app/static` (relatif au module),
`<resources>/static`, `<resources>/app/static` → le bundler peut préserver le
layout **ou** aplatir à la racine.

---

## 5. Future bundler — exigences

Le futur outil (PyInstaller/Nuitka/…) devra :
- embarquer le runtime Python + les dépendances (`Flask`, `lxml`, etc.) ;
- **inclure `lxml`** (extension native, wheel `win_amd64`) ;
- **inclure les XSD** en tant que data files (section 4) ;
- **inclure le frontend `dist`** sous `frontend/` (ou via `XMLFORGE_FRONTEND_DIST`) ;
- **ne jamais inclure** : `.env` réel, `secrets.env`, `backend/data/**`,
  `backend/uploads`, `backend/exports`, logs, tests, `node_modules` ;
- conserver `sys.frozen`/`sys._MEIPASS` détectables (`paths.is_frozen()`).

---

## 6. Future installer — recommandations

- Installation des binaires dans `C:\Program Files\XMLForge\` (lecture seule).
- Raccourci lançant l'EXE → le serveur démarre Flask (`:5000`) + TCP (`:3307`)
  et le frontend est servi par Flask ; ouvrir le navigateur sur `http://localhost:5000`.
- **Désinstallation** : supprimer l'application + raccourcis ; **conserver**
  `%LOCALAPPDATA%\XMLForge\data\` et `config\` (option explicite « supprimer mes
  données » pour l'utilisateur).
- **Mise à jour / réinstallation** : remplacer les fichiers applicatifs,
  conserver `data/` + `config/` (bases XML et secrets inchangés).

---

## 7. Première exécution (flux prévu)

```text
XMLForge.exe
    ↓
prepare_runtime()       → crée %LOCALAPPDATA%\XMLForge\{data,tmp,logs,config}
    ↓
ensure_secrets()        → génère/persiste SECRET_KEY, JWT_SECRET_KEY (si absents)
    ↓
bootstrap_if_needed()   → crée security.xml (rôles admin/user), catalog.xml, history.xml
    ↓
ensure_admin()          → crée/promeut l'administrateur (paramètres explicites, aucun dur)
    ↓
Flask :5000 (frontend servi) + TCP :3307
```

En développement, le flux interactif existant reste inchangé :
`flask xml-bootstrap` puis `flask create-admin` puis `python run.py`.
La commande équivalente non interactive est :
`flask init-app --email <EMAIL> --name <NOM> --password <MOT_DE_PASSE>`.

---

## 8. Tests (résultats exacts)

| Suite | Commande | Résultat |
|---|---|---|
| Backend complet | `.venv/bin/python -m pytest -q` | **349 passed** (334 + 15 nouveaux) en 58,48 s |
| Nouveaux tests packaging | `pytest tests/test_packaging.py` | **15 passed** |
| E2E backend | `pytest tests/e2e -q` | **1 passed** |
| Frontend | `npm test` | **10 passed | 1 skipped** |
| Lint | `npm run lint` | **0 erreur, 3 warnings** (préexistants) |
| Build | `npm run build` | **OK** |
| Mode installé (live) | `init-app` + serveur réel | bootstrap **created** puis **skipped** (idempotent), admin créé puis mis à jour |
| Frontend servi | `GET /` en mode installé | **200** index React ; `/api/nope` → **404 JSON** ; `/health` → **200** |
| TCP 3307 (client officiel) | AUTH/USE/CREATE/INSERT/SELECT/ROLLBACK/COMMIT | **OK** |
| Persistance | arrêt → redémarrage | données conservées (count=3), secrets identiques |
| SQLite check | `find` sur l'installation de test | **0** fichier `.db`/`.sqlite` |
| CWD indépendant | sous-processus depuis un CWD arbitraire | chemins indépendants du CWD |
| Frozen simulation | sous-processus `sys.frozen` + `LOCALAPPDATA` | données sous `%LOCALAPPDATA%\XMLForge`, ressources sous le bundle |
| `pip check` | — | No broken requirements found |

---

## 9. Limitations restantes (à traiter pendant la phase de packaging uniquement)

- Choix du bundler et de l'installateur (hors périmètre).
- Création de l'EXE, des raccourcis, icônes, signature (hors périmètre).
- Serveur HTTP : Werkzeug conservé (aucune dépendance ajoutée) ; si un service
  Windows/tray est requis, prévoir un WSGI de production (ex. waitress) + gestion
  de signal — décision laissée au packaging.
- Arrêt propre du processus Flask détaché : `TCPServer.stop()` existe déjà ;
  l'arrêt de Flask en processus sans console devra être géré par le launcher.
- Mise à jour de schéma XML (compatibilité XSD ascendante entre versions).
- **Observation pré-existante (non liée au packaging)** : `CREATE DATABASE` via
  TCP exige une base déjà sélectionnée (il faut créer la base via REST ou
  sélectionner une base existante d'abord). Comportement inchangé par cette phase.

---

## 10. Confirmation finale

- ✅ Aucun `.exe` ni installateur créé ; aucun bundler installé.
- ✅ Port TCP **3307** inchangé ; port HTTP **5000** conservé par défaut.
- ✅ XMLForge reste **XML-only** (aucun SQLite/SQLAlchemy/MySQL ; 0 fichier `.db`/`.sqlite`).
- ✅ Moteur XML, protocole TCP, permissions PERSONAL/COMMON, transactions, REST,
  client Python : **inchangés fonctionnellement**.
- ✅ Architecture préservée : Flask + TCP dans un seul processus.
