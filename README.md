# XMLForge — Serveur de base de données relationnelle 100 % XML

XMLForge est un **SGBD relationnel dont le stockage est exclusivement XML**
(sans SQLite, sans SQLAlchemy, sans ORM). Une application externe s'y connecte
via **REST** (Flask `:5000`) ou **TCP** (`:3307`, client Python officiel), sans
jamais accéder aux fichiers XML.

## Architecture

```
Applications externes
    ├── Client Python (xmlforge/) ── TCP :3307
    └── Frontend React (xmlforge-react/) ── REST :5000
                    │
XMLForge Server (backend/)
    ├── Services (auth, permission unique ACL, database, table, column, row…)
    ├── Control Plane XML : security.xml · catalog.xml · history.xml · audit/YYYY-MM.xml
    ├── Data Plane XML     : data/xml/<id>_<slug>.xml
    ├── XML Native Engine  : SELECT/INSERT/UPDATE/DELETE/DDL/agrégats/JOIN/index/PK/FK/UNIQUE
    └── XML Storage        : verrous, écriture atomique, version, checksum, snapshot/rollback
```

REST et TCP utilisent **les mêmes services et la même logique de permissions**
(PERSONAL / COMMON `VIEW`·`EDIT`·`MANAGE`, owner, grants).

## Démarrage rapide

```bash
# Backend (REST :5000 + TCP :3307)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app run.py xml-bootstrap   # crée security.xml, catalog.xml, history.xml
flask --app run.py create-admin    # premier compte administrateur
python run.py

# Frontend (Vite :5173)
cd ../xmlforge-react
npm install && npm run dev
```

## Client Python

```python
from xmlforge import connect

with connect(host="localhost", port=3307, user="<VOTRE_TCP_USERNAME>",
             password="<VOTRE_TCP_PASSWORD>") as db:
    db.execute("USE Bibliotheque")
    for row in db.query("SELECT * FROM books ORDER BY id").rows:
        print(row)
```

## Tests

```bash
cd backend && python -m pytest -q          # suite complète (334 tests)
cd backend && python -m pytest tests/e2e   # E2E TCP réel
cd xmlforge-react && npm test              # frontend (vitest)
cd xmlforge-react && npm run lint && npm run build
```

## Documentation

| Document | Sujet |
|---|---|
| [`XMLFORGE_SERVER.md`](XMLFORGE_SERVER.md) | serveur, architecture, démarrage, configuration |
| [`XMLFORGE_PROTOCOL.md`](XMLFORGE_PROTOCOL.md) | protocole TCP `[type:1][len:4 BE][JSON]` |
| [`XMLFORGE_SQL.md`](XMLFORGE_SQL.md) | dialecte SQL réellement supporté |
| [`XMLFORGE_CLIENT.md`](XMLFORGE_CLIENT.md) | client Python `xmlforge/` |
| [`XMLFORGE_TRANSACTIONS.md`](XMLFORGE_TRANSACTIONS.md) | transactions TCP `BEGIN/COMMIT/ROLLBACK` |
| [`XMLFORGE_CONCURRENCY.md`](XMLFORGE_CONCURRENCY.md) | verrous, atomicité, limites documentées |
| [`XMLFORGE_ERRORS.md`](XMLFORGE_ERRORS.md) | codes d'erreur TCP (`error_code`) et REST |
| [`backend/README.md`](backend/README.md) | détails backend (routes, stockage XML) |
| [`PHASE_7_POST_AUDIT_REPORT.md`](PHASE_7_POST_AUDIT_REPORT.md) | audit post-Phase 7 |
| [`POST_AUDIT_FIX_REPORT.md`](POST_AUDIT_FIX_REPORT.md) | corrections post-audit |

> Les fichiers `QUICKSTART.md`, `README_TCP_COMPLETE.md`,
> `XML_BACKEND_MODE.md`, `SQLITE_DEPENDENCIES.md`,
> `MANUEL_TEST_VALIDATION_XMLFORGE.md` et les rapports `PHASE_4/5/6_*.md` sont
> des **archives historiques** (architecture antérieure SQLite/SQLAlchemy).
